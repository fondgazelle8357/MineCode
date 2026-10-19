"""Original small fixtures; wrapper simulators exercise subprocesses without Minecraft."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from minecode_runtime.gradle import stop_tree
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
from minecode_runtime.diagnostics import analyze
from minecode_runtime.gradle import Runtime, validate_task, wrapper_command
from minecode_runtime.inspection import inspect
from minecode_runtime.models import FailureEnvironment
from minecode_runtime.server import create_server

FABRIC_BUILD = """plugins { id 'fabric-loom' version '1.10.5' }
minecraft "com.mojang:minecraft:$minecraft_version"
modImplementation "net.fabricmc:fabric-loader:$loader_version"
modImplementation "net.fabricmc.fabric-api:fabric-api:$fabric_version"
mappings "net.fabricmc:yarn:$yarn_mappings:v2"
java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
"""


class Fixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minecode & fixture ")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def fabric(self):
        self.write("build.gradle", FABRIC_BUILD)
        self.write("settings.gradle", "rootProject.name = 'neutral-fixture'")
        self.write("gradle.properties", "minecraft_version=1.21.5\nloader_version=0.16.14\nfabric_version=0.119.5+1.21.5\nyarn_mappings=1.21.5+build.1\n")
        self.write("gradle/wrapper/gradle-wrapper.properties", "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.12-bin.zip")
        self.write("src/main/resources/fabric.mod.json", json.dumps({
            "id": "neutral_fixture", "environment": "client", "mixins": ["neutral.mixins.json"],
            "entrypoints": {"client": ["example.NeutralClient"]}, "depends": {"minecraft": ">=1.21"}}))
        self.write("src/client/java/example/NeutralClient.java", "// Metadata fixture, not Minecraft code.\n")

    def wrapper(self, mode="success"):
        self.write("simulate.py", """
import os, pathlib, sys, time
pathlib.Path('child.pid').write_text(str(os.getpid()))
mode = pathlib.Path('mode.txt').read_text()
task = next((a for a in sys.argv[1:] if not a.startswith('--')), '')
print('ARGS:' + '|'.join(sys.argv[1:]), flush=True)
if task == 'tasks':
    print('build - Assemble project')
    if mode != 'no-client':
        print('runClient - Run development client')
elif mode == 'failure':
    print(r'C:\\project space\\src\\Example.java:7: error: cannot find symbol', file=sys.stderr)
    sys.exit(1)
elif mode == 'timeout':
    print('Waiting for test timeout', flush=True)
    time.sleep(30)
elif mode == 'large-failure':
    print('x' * 150000)
    print('y' * 150000, file=sys.stderr)
    sys.exit(1)
elif mode == 'large':
    print('x' * 150000)
else:
    pathlib.Path('build/libs').mkdir(parents=True, exist_ok=True)
    pathlib.Path('build/libs/neutral.jar').write_bytes(b'original test artifact')
    print('BUILD SUCCESSFUL')
""")
        self.write("mode.txt", mode)
        if os.name == "nt":
            # Quoted Python path is fixture-owned content; the runtime supplies no shell text.
            self.write("gradlew.bat", '@echo off\n"' + sys.executable + '" simulate.py %*\n')
        else:
            path = self.write("gradlew", '#!/bin/sh\nexec "' + sys.executable + '" simulate.py "$@"\n')
            path.chmod(0o755)


class InspectionTests(Fixture, unittest.TestCase):
    def test_no_gradle_and_unknown_fields(self):
        result = inspect(self.root)
        self.assertFalse(result.detection.gradle_detected)
        self.assertEqual(result.detection.project_type, "unknown")
        self.assertIsNone(result.minecraft_version)
        self.assertIsNone(result.java_version)

    def test_basic_gradle(self):
        self.write("build.gradle.kts", 'plugins { id("java") }\n')
        self.assertTrue(inspect(self.root).detection.java_detected)
        self.assertTrue(inspect(self.root).detection.gradle_detected)

    def test_fabric_profile(self):
        self.fabric()
        p = inspect(self.root)
        self.assertEqual(p.detection.project_type, "fabric-client")
        self.assertEqual(p.minecraft_version, "1.21.5")
        self.assertEqual(p.fabric_loader_version, "0.16.14")
        self.assertEqual(p.fabric_api_version, "0.119.5+1.21.5")
        self.assertEqual(p.java_version, "21")
        self.assertEqual(p.gradle_version, "8.12")
        self.assertEqual(p.loom_version, "1.10.5")
        self.assertEqual(p.mappings_type, "yarn")
        self.assertEqual(p.mappings_version, "1.21.5+build.1")
        self.assertEqual(p.project_name, "neutral-fixture")
        self.assertEqual(p.mod_id, "neutral_fixture")
        self.assertIn("src/client/java", p.client_source_roots)
        self.assertEqual(p.mixin_configs, ["neutral.mixins.json"])
        self.assertEqual(p.entrypoints["client"], ["example.NeutralClient"])

    def test_kotlin_version_catalog_fabric_profile(self):
        self.write("build.gradle.kts", """plugins {
    alias(libs.plugins.fabric.loom)
}
dependencies {
    minecraft(libs.minecraft)
    mappings(variantOf(libs.yarn.mappings) { classifier("v2") })
    modImplementation(libs.fabric.loader)
    modImplementation(libs.fabric.api)
}
""")
        self.write("gradle/libs.versions.toml", """[versions]
minecraft = "1.21.4"
loader = "0.16.10"
yarn = "1.21.4+build.8"
loom = "1.8.12"

[libraries]
minecraft = { module = "com.mojang:minecraft", version.ref = "minecraft" }
fabric-loader = { group = "net.fabricmc", name = "fabric-loader", version.ref = "loader" }
fabric-api = { module = "net.fabricmc.fabric-api:fabric-api", version = "0.110.5+1.21.4" }
yarn-mappings = { module = "net.fabricmc:yarn", version.ref = "yarn" }

[plugins]
fabric-loom = { id = "fabric-loom", version.ref = "loom" }
""")
        p = inspect(self.root)
        self.assertEqual(p.detection.project_type, "fabric-mod")
        self.assertEqual(p.minecraft_version, "1.21.4")
        self.assertEqual(p.fabric_loader_version, "0.16.10")
        self.assertEqual(p.fabric_api_version, "0.110.5+1.21.4")
        self.assertEqual(p.loom_version, "1.8.12")
        self.assertEqual((p.mappings_type, p.mappings_version), ("yarn", "1.21.4+build.8"))
        self.assertIsNone(p.java_version)
        self.assertIn(str(Path("gradle") / "libs.versions.toml"), p.evidence["minecraft_version"])

    def test_version_catalog_identity_and_conflict(self):
        self.write("build.gradle.kts", """plugins { alias(libs.plugins.fabric.loom) }
dependencies {
    minecraft(libs.minecraft)
    minecraft(libs.actual.game)
    minecraft("com.mojang:minecraft:$minecraft_version")
}
""")
        self.write("gradle.properties", "minecraft_version=1.20.1\n")
        self.write("gradle/libs.versions.toml", """[versions]
modern = "1.21.4"

[libraries]
minecraft = { module = "com.example:not-minecraft", version = "9.9.9" }
actual-game = { module = "com.mojang:minecraft", version.ref = "modern" }

[plugins]
fabric-loom = { id = "com.example.not-loom", version = "9.9.9" }
""")
        p = inspect(self.root)
        self.assertTrue(p.detection.minecraft_detected)
        self.assertFalse(p.detection.fabric_detected)
        self.assertIsNone(p.minecraft_version)
        self.assertEqual(p.evidence["minecraft_version"],
                         ["build.gradle.kts", str(Path("gradle") / "libs.versions.toml")])
        self.assertTrue(any("Conflicting minecraft_version" in warning for warning in p.warnings))

    def test_malformed_version_catalog_warns(self):
        self.write("build.gradle.kts", "plugins { alias(libs.plugins.fabric.loom) }\n")
        self.write("gradle/libs.versions.toml", '[versions\nminecraft = "1.21.4"\n')
        p = inspect(self.root)
        self.assertFalse(p.detection.fabric_detected)
        self.assertTrue(any("Invalid TOML: gradle/libs.versions.toml" in warning for warning in p.warnings))

    def test_conflicting_and_computed_versions_unknown(self):
        self.write("gradle.properties", "minecraft_version=1.21.5\n")
        self.write("build.gradle", 'minecraft "com.mojang:minecraft:1.20.1"\nminecraft "com.mojang:minecraft:$minecraft_version"\n')
        p = inspect(self.root)
        self.assertIsNone(p.minecraft_version)
        self.assertTrue(any("Conflicting" in w for w in p.warnings))
        self.write("gradle.properties", "minecraft_version=" + "$" + "{dynamic}\n")
        self.write("build.gradle", "version = calculateVersion()\n")
        self.assertIsNone(inspect(self.root).minecraft_version)

    def test_complete_property_identifier_only(self):
        self.write("gradle.properties", "mc=1.21.5\n")
        self.write("build.gradle", 'minecraft "com.mojang:minecraft:$mc_version"\n')
        self.assertIsNone(inspect(self.root).minecraft_version)
        self.write("gradle.properties", "mc_version=1.21.5\n")
        self.assertEqual(inspect(self.root).minecraft_version, "1.21.5")

    def test_unused_properties_and_unrelated_coordinates_are_not_versions(self):
        self.write("gradle.properties", "minecraft_version=1.20.1\nyarn_mappings=1.20.1+build.10\nloader_version=0.1\n")
        for script in ('plugins { id "java" }', 'println("com.mojang:minecraft:1.21.11")',
                       'def example = """minecraft \'com.mojang:minecraft:1.21.11\'"""',
                       'minecraft("com.mojang:minecraft:1.21.11" + suffix)'):
            with self.subTest(script=script):
                self.write("build.gradle", script)
                profile = inspect(self.root)
                self.assertIsNone(profile.minecraft_version)
                self.assertIsNone(profile.mappings_type)
                self.assertIsNone(profile.fabric_loader_version)

    def test_used_literal_overrides_unused_property_hint(self):
        self.write("gradle.properties", "minecraft_version=1.20.1\n")
        self.write("build.gradle.kts", 'dependencies { minecraft("com.mojang:minecraft:1.21.11") }')
        self.assertEqual(inspect(self.root).minecraft_version, "1.21.11")

    def test_project_property_interpolation_is_supported(self):
        self.write("gradle.properties", "minecraft_version=1.21.11\n")
        self.write("build.gradle", 'dependencies { minecraft "com.mojang:minecraft:${project.minecraft_version}" }')
        self.assertEqual(inspect(self.root).minecraft_version, "1.21.11")

    def test_catalog_references_in_messages_are_not_dependencies(self):
        self.write("gradle/libs.versions.toml", '[libraries]\nminecraft = "com.mojang:minecraft:1.21.11"\n')
        self.write("build.gradle.kts", 'println(libs.minecraft)\nprintln("minecraft(libs.minecraft)")\n')
        self.assertIsNone(inspect(self.root).minecraft_version)

    def test_single_quoted_coordinate_does_not_interpolate(self):
        self.write("gradle.properties", "minecraft_version=1.21.5\ncustom_version=1.20.1\n")
        # Use a noncanonical property to ensure no direct property evidence supplies a version.
        self.write("gradle.properties", "custom_version=1.20.1\n")
        self.write("build.gradle", "minecraft 'com.mojang:minecraft:$custom_version'\n")
        self.assertIsNone(inspect(self.root).minecraft_version)
        self.write("build.gradle", 'minecraft "com.mojang:minecraft:$custom_version"\n')
        self.assertEqual(inspect(self.root).minecraft_version, "1.20.1")

    def test_legacy_java_versions(self):
        for token in ['"1.8"', "JavaVersion.VERSION_1_8"]:
            self.write("build.gradle", "sourceCompatibility = " + token)
            self.assertEqual(inspect(self.root).java_version, "8")

    def test_comments_are_not_metadata(self):
        self.write("build.gradle", "// minecraft 'com.mojang:minecraft:1.20.1'\n/* plugins { id 'fabric-loom' } */\nplugins { id 'java' }")
        p = inspect(self.root)
        self.assertFalse(p.detection.fabric_detected)
        self.assertIsNone(p.minecraft_version)

    def test_bad_descriptor(self):
        self.write("src/main/resources/fabric.mod.json", "{")
        self.assertTrue(any("Invalid JSON" in w for w in inspect(self.root).warnings))

    def test_outside_metadata_link(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "build.gradle"
            target.write_text("plugins { id 'fabric-loom' }")
            try:
                (self.root / "build.gradle").symlink_to(target)
            except OSError:
                self.skipTest("OS does not permit fixture symlinks")
            self.assertFalse(inspect(self.root).detection.fabric_detected)


class DiagnosisTests(unittest.TestCase):
    def test_java_versions(self):
        d = analyze("Project requires Java 21; currently using Java 17")
        self.assertEqual(d.category, "java-version")
        self.assertEqual((d.expected_java, d.observed_java), ("21", "17"))

    def test_gradle_plugin_jvm_requirement_overrides_dependency_category(self):
        d = analyze(
            "Could not resolve net.fabricmc:fabric-loom:1.18.2.\n"
            "Dependency requires at least JVM runtime version 25. This build uses a Java 22 JVM.")
        self.assertEqual(d.category, "java-version")
        self.assertEqual((d.expected_java, d.observed_java), ("25", "22"))
        self.assertEqual(d.dependency, "net.fabricmc:fabric-loom:1.18.2")
        self.assertIn("Java 25", d.next_step)
        self.assertIn("target can be different", d.next_step)

    def test_controlled_type_error_reports_file_and_error(self):
        d = analyze(r"C:\validation\ExampleMod.java:32: error: incompatible types: String cannot be converted to int")
        self.assertEqual(d.category, "compiler")
        self.assertEqual(d.affected_file, r"C:\validation\ExampleMod.java")
        self.assertIn("String cannot be converted to int", d.important_error)
        self.assertIn("first compiler error", d.next_step)

    def test_windows_compiler_path(self):
        d = analyze(r"C:\Project with spaces\src\Foo.java:42: error: cannot find symbol")
        self.assertEqual(d.category, "compiler")
        self.assertEqual(d.migration_layer, "ordinary-java")
        self.assertEqual(d.affected_file, r"C:\Project with spaces\src\Foo.java")
        self.assertEqual(d.affected_line, 42)

    def test_categories_and_unknown(self):
        samples = {"mixin": "org.spongepowered.asm.mixin.throwables.InvalidMixinException: target missing",
                   "dependency": "Could not resolve net.fabricmc:fabric-loader:0.16.14.",
                   "gradle-configuration": "A problem occurred evaluating root project",
                   "compiler": "Compilation failed"}
        for category, output in samples.items():
            with self.subTest(category=category):
                self.assertEqual(analyze(output).category, category)
        self.assertEqual(analyze("unclassified").confidence, "unknown")

    def test_oversized_input(self):
        with self.assertRaises(ValueError):
            analyze("x" * 128001)


class MigrationDiagnosisTests(unittest.TestCase):
    environment = FailureEnvironment(
        minecraft="1.21.4", loader="fabric-0.16.10", fabric_api="0.110.5+1.21.4",
        loom="1.8.12", mappings="yarn-1.21.4+build.8", side="client", java="21", gradle="8.10")

    def test_preserves_ordinary_java_symbol_without_claiming_migration(self):
        result = analyze(
            "/project/src/main/java/example/Feature.java:18: error: cannot find symbol\n"
            "  symbol:   variable localCounter\n"
            "  location: class Feature\n"
            "/project/src/client/java/example/Hud.java:30: error: package net.fabricmc.fabric.api does not exist")
        self.assertEqual((result.category, result.migration_layer), ("compiler", "ordinary-java"))
        self.assertEqual(result.affected_line, 18)
        self.assertEqual(result.migration_details["unresolved_symbol"], "localCounter")
        self.assertNotIn("mapping migration", result.likely_root_cause.lower())
        runtime = analyze("java.lang.NoSuchMethodError: example.library.Widget.render()V")
        self.assertEqual((runtime.category, runtime.migration_layer),
                         ("symbol-unavailable", "unknown"))
        self.assertEqual(runtime.migration_details["owner"], "example.library.Widget")
        self.assertEqual(runtime.migration_details["unresolved_symbol"], "render()V")

    def test_distinguishes_vanilla_and_fabric_namespaces(self):
        vanilla = analyze(
            "/project/src/client/java/example/Hud.java:31: error: cannot find symbol\n"
            "import net.minecraft.client.gui.DrawContext;\n"
            "  symbol:   method drawTexture(RenderLayer,int,int)\n"
            "  location: class net.minecraft.client.gui.DrawContext",
            self.environment)
        fabric = analyze(
            "/project/src/client/java/example/Hud.java:44: error: package "
            "net.fabricmc.fabric.api.client.rendering.v1 does not exist\n"
            "import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;",
            self.environment)
        self.assertEqual((vanilla.category, vanilla.migration_layer),
                         ("minecraft-symbol", "mappings-vanilla"))
        self.assertEqual(vanilla.migration_details["unresolved_symbol"],
                         "drawTexture(RenderLayer,int,int)")
        self.assertEqual((fabric.category, fabric.migration_layer),
                         ("fabric-api", "fabric-loader-api"))
        self.assertEqual(fabric.migration_details["package"],
                         "net.fabricmc.fabric.api.client.rendering.v1")
        self.assertIn("minecraft 1.21.4", vanilla.next_step)
        self.assertIn("fabric_api 0.110.5+1.21.4", fabric.next_step)

    def test_reported_server_side_can_identify_client_reachability(self):
        result = analyze(
            "/project/src/main/java/example/CommonInit.java:9: error: package net.minecraft.client does not exist\n"
            "import net.minecraft.client.MinecraftClient;",
            FailureEnvironment(minecraft="1.21.4", loader="fabric", side="dedicated-server"))
        self.assertEqual((result.category, result.migration_layer),
                         ("side-source-set", "side-source-set"))
        self.assertIn("client-only", result.likely_root_cause)

    def test_build_foundation_failures_are_separate_from_source_migration(self):
        result = analyze("The minimum supported Gradle version is 8.10. Current version is 8.7")
        self.assertEqual((result.category, result.migration_layer),
                         ("gradle-version", "build-toolchain"))
        self.assertIn("wrapper", result.next_step)

    def test_representative_fabric_migration_keeps_layers_and_does_not_guess(self):
        outputs = {
            "vanilla": (
                "/project/src/client/java/example/Hud.java:31: error: cannot find symbol\n"
                "import net.minecraft.client.gui.DrawContext;\n"
                "  symbol: method drawTexture(RenderLayer,int,int)\n"
                "  location: class net.minecraft.client.gui.DrawContext"),
            "fabric": (
                "/project/src/client/java/example/ClientInit.java:22: error: package "
                "net.fabricmc.fabric.api.client.rendering.v1 does not exist\n"
                "import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;"),
            "mixin": (
                "InvalidInjectionException: @Inject annotation on renderHud could not find any targets matching "
                "renderHud(Lnet/minecraft/client/gui/DrawContext;F)V in net.minecraft.client.gui.hud.InGameHud"),
        }
        results = {name: analyze(output, self.environment) for name, output in outputs.items()}
        self.assertEqual(results["vanilla"].migration_layer, "mappings-vanilla")
        self.assertEqual(results["fabric"].migration_layer, "fabric-loader-api")
        self.assertEqual(results["mixin"].migration_layer, "mixin")
        self.assertEqual(results["mixin"].mixin_failure, "target-not-found")
        self.assertEqual(results["mixin"].mixin_details["target_member"], "renderHud")
        for result in results.values():
            self.assertNotIn("renamed to", result.likely_root_cause.lower())


class MixinDiagnosisTests(unittest.TestCase):
    def test_distinguishes_supported_mixin_failure_modes(self):
        samples = {
            'target-not-found':
                'InvalidInjectionException: @Inject annotation on init could not find any targets matching missingLoadLevel',
            'descriptor-handler-mismatch':
                'InvalidInjectionException: @Redirect handler method redirectUse has an invalid signature. '
                'Expected (Lnet/minecraft/world/World;)V but Found (Lnet/minecraft/world/World;)Z',
            'injection-point-mismatch':
                'InjectionError: Critical injection failure: @Inject failed injection check, (0/1) succeeded',
            'mappings-remap':
                "MixinApplyError: Reference map 'example-refmap.json' could not be read; no obfuscation mapping was found",
            'side-configuration':
                'MixinApplyError: attempted to load client target for invalid dist DEDICATED_SERVER',
        }
        for expected, output in samples.items():
            with self.subTest(expected=expected):
                result = analyze(output)
                self.assertEqual(result.category, 'mixin')
                self.assertEqual(result.mixin_failure, expected)
                self.assertTrue(result.next_step)

    def test_preserves_selector_injection_point_ordinal_and_counts(self):
        result = analyze(
            'InjectionError: [example.mixins.json:example.mixin.CombatMixin] Critical injection failure: '
            '@Redirect annotation on redirectAttack failed injection check, (0/1) succeeded. '
            '@At(value="INVOKE", target="Lnet/minecraft/client/network/ClientPlayerEntity;attack()V", ordinal=1)')
        self.assertEqual(result.mixin_failure, 'injection-point-mismatch')
        self.assertEqual(result.mixin_details['mixin'], 'example.mixin.CombatMixin')
        self.assertEqual(result.mixin_details['config'], 'example.mixins.json')
        self.assertEqual(result.mixin_details['injector'], '@Redirect')
        self.assertEqual(result.mixin_details['handler'], 'redirectAttack')
        self.assertEqual(result.mixin_details['injection_point'], 'INVOKE')
        self.assertEqual(result.mixin_details['ordinal'], '1')
        self.assertEqual((result.mixin_details['found_count'], result.mixin_details['expected_count']), ('0', '1'))
        self.assertIn('ClientPlayerEntity;attack()V', result.mixin_details['at_target'])
        self.assertNotIn('target_member', result.mixin_details)

    def test_preserves_target_class_and_handler_descriptor_mismatch(self):
        missing_class = analyze(
            'InvalidMixinException: @Mixin target net.minecraft.client.gui.hud.InGameHud was not found')
        self.assertEqual(missing_class.mixin_failure, 'target-not-found')
        self.assertEqual(missing_class.mixin_details['target_class'],
                         'net.minecraft.client.gui.hud.InGameHud')

        descriptor = analyze(
            'InvalidInjectionException: @Redirect handler method redirectUse has an invalid signature. '
            'Expected (Lnet/minecraft/world/World;)V but Found (Lnet/minecraft/world/World;)Z')
        self.assertEqual(descriptor.mixin_failure, 'descriptor-handler-mismatch')
        self.assertEqual(descriptor.mixin_details['handler'], 'redirectUse')
        self.assertEqual(descriptor.mixin_details['expected_descriptor'],
                         '(Lnet/minecraft/world/World;)V')
        self.assertEqual(descriptor.mixin_details['found_descriptor'],
                         '(Lnet/minecraft/world/World;)Z')
        self.assertNotIn('target_member', descriptor.mixin_details)

    def test_preserves_version_migration_target_and_descriptor(self):
        result = analyze(
            'InvalidInjectionException: @Inject annotation on renderHud could not find any targets matching '
            'renderHud(Lnet/minecraft/client/gui/DrawContext;F)V in net.minecraft.client.gui.hud.InGameHud')
        self.assertEqual(result.mixin_failure, 'target-not-found')
        self.assertEqual(result.mixin_details['injector'], '@Inject')
        self.assertEqual(result.mixin_details['target_class'], 'net.minecraft.client.gui.hud.InGameHud')
        self.assertEqual(result.mixin_details['target_member'], 'renderHud')
        self.assertEqual(result.mixin_details['descriptor'], '(Lnet/minecraft/client/gui/DrawContext;F)V')
        self.assertIn('does not prove', result.likely_root_cause)

    def test_generic_mixin_failure_remains_unclassified(self):
        result = analyze('MixinTransformerError: Unexpected critical problem while transforming a class')
        self.assertEqual(result.category, 'mixin')
        self.assertEqual(result.mixin_failure, 'unclassified')
        self.assertEqual(result.mixin_details, {})
        self.assertIn('does not distinguish', result.likely_root_cause)


class ExecutionTests(Fixture, unittest.IsolatedAsyncioTestCase):
    async def test_default_disabled_and_missing_wrapper(self):
        result = await Runtime(self.root).run_gradle("build")
        self.assertEqual(result.state, "blocked")
        result = await Runtime(self.root, allow_execution=True).build_project()
        self.assertIn("Missing local", result.execution.summary)

    async def test_successful_simulated_build(self):
        self.wrapper()
        result = await Runtime(self.root, allow_execution=True).build_project()
        self.assertTrue(result.execution.success)
        self.assertEqual(result.execution.exit_code, 0)
        self.assertIn("--offline", result.execution.stdout)
        self.assertTrue(result.artifacts[0].changed_during_build)
        self.assertFalse(result.runtime_verified)
        again = await Runtime(self.root, allow_execution=True).build_project()
        self.assertFalse(again.runtime_verified)

    async def test_failed_simulated_build(self):
        self.wrapper("failure")
        result = await Runtime(self.root, allow_execution=True).build_project()
        self.assertFalse(result.execution.success)
        self.assertEqual(result.execution.exit_code, 1)
        self.assertEqual(result.execution.diagnosis.category, "compiler")
        self.assertIn("Example.java", result.execution.stderr)

    async def test_task_injection_and_timeout_rejected(self):
        self.wrapper()
        runtime = Runtime(self.root, allow_execution=True)
        for task in ["build & echo hacked", "build;id", "--init-script=x", "../build", "%PATH%", "test\nbuild", "tasks", "clean"]:
            with self.subTest(task=task), self.assertRaises(ValueError):
                await runtime.run_gradle(task)
        for value in [0, 601, True, 1.5]:
            with self.assertRaises(ValueError):
                await runtime.run_gradle("build", value)
        for task in ["build", ":client:build", "client:runClient"]:
            validate_task(task)

    async def test_nonexistent_client(self):
        self.fabric()
        self.wrapper("no-client")
        result = await Runtime(self.root, allow_execution=True).run_client()
        self.assertEqual(result.startup_state, "task_missing")
        self.assertFalse(result.gameplay_verified)
        self.assertFalse((self.root / "build").exists())

    async def test_client_discovery_and_bounded_launch(self):
        self.fabric()
        self.wrapper()
        result = await Runtime(self.root, allow_execution=True).run_client()
        self.assertTrue(result.discovery.success)
        self.assertTrue(result.execution.success)
        self.assertEqual(result.startup_state, "process_exited")
        self.assertFalse(result.gameplay_verified)

    async def test_timeout_and_partial_output(self):
        self.wrapper("timeout")
        result = await Runtime(self.root, allow_execution=True).run_gradle("test", 1)
        self.assertEqual(result.state, "timed_out")
        self.assertLess(result.elapsed_seconds, 8)
        self.assertIn("Waiting", result.stdout)

    async def test_output_bounded(self):
        self.wrapper("large")
        result = await Runtime(self.root, allow_execution=True).run_gradle("classes")
        self.assertTrue(result.success)
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout), 64000)

    async def test_failure_with_both_streams_large(self):
        self.wrapper("large-failure")
        result = await Runtime(self.root, allow_execution=True).build_project()
        self.assertEqual(result.execution.state, "failed")
        self.assertEqual(result.execution.diagnosis.confidence, "unknown")
        self.assertTrue(result.execution.output_truncated)

    async def test_cancellation_cleans_process_and_releases_lock(self):
        self.wrapper("timeout")
        runtime = Runtime(self.root, allow_execution=True)
        task = asyncio.create_task(runtime.run_gradle("test", 30))
        for _ in range(100):
            if (self.root / "child.pid").exists():
                break
            await asyncio.sleep(0.02)
        self.assertTrue((self.root / "child.pid").exists())
        pid = int((self.root / "child.pid").read_text())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        if os.name == "nt":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(handle)
                self.assertNotEqual(code.value, 259, "Fixture child remains active")
        else:
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)
        self.write("mode.txt", "success")
        result = await asyncio.wait_for(runtime.run_gradle("test", 5), 8)
        self.assertTrue(result.success)

    async def test_uncertain_cleanup_warns(self):
        self.wrapper("timeout")

        async def kill_but_report_uncertain(process):
            await stop_tree(process)
            return False

        with patch("minecode_runtime.gradle.stop_tree", side_effect=kill_but_report_uncertain):
            result = await Runtime(self.root, allow_execution=True).run_gradle("test", 1)
        self.assertTrue(any("could not be confirmed" in warning for warning in result.warnings))

    async def test_network_flag_explicit(self):
        self.wrapper()
        result = await Runtime(self.root, allow_execution=True, allow_network=True).run_gradle("test")
        self.assertNotIn("--offline", result.stdout)

    async def test_windows_command_keeps_path_outside_shell_text(self):
        self.write("gradlew.bat", "@echo off\n")
        command = wrapper_command(self.root.resolve(), ":client:build", True, windows=True)
        self.assertEqual(command[-1], r".\gradlew.bat --no-daemon --console=plain --offline :client:build")
        self.assertNotIn(str(self.root), command[-1])

    @unittest.skipUnless(os.name == "nt", "Windows wrapper search regression")
    async def test_windows_wrapper_runs_without_current_directory_search(self):
        self.wrapper()
        with patch.dict(os.environ, {"NoDefaultCurrentDirectoryInExePath": "1"}):
            result = await Runtime(self.root, allow_execution=True).build_project()
        self.assertTrue(result.execution.success, result.execution.stderr)
        self.assertIn("BUILD SUCCESSFUL", result.execution.stdout)


class MCPTests(Fixture, unittest.IsolatedAsyncioTestCase):
    async def test_server_environment_is_context_not_a_failure_over_stdio(self):
        environment = {'minecraft': '1.21.11', 'side': 'dedicated-server'}
        label = 'Environment: DEDICATED_SERVER\n'
        missing = 'InvalidInjectionException: @Inject annotation on init could not find any targets matching missingLoadLevel'
        cases = [
            (label + '[Server thread/INFO]: Done (3.2s)! For help, type "help"', 'unknown', None),
            (label + 'java.lang.IllegalArgumentException: port must be positive', 'unknown', None),
            ('RuntimeException: Attempted to load class net/minecraft/client/gui/screens/Screen for invalid dist DEDICATED_SERVER',
             'side-source-set', None),
            ('RuntimeException: Cannot load class net.minecraft.client.MinecraftClient in environment type SERVER',
             'side-source-set', None),
            (label * 8 + missing, 'mixin', 'target-not-found'),
            (label + 'MixinApplyError: attempted to load client target for invalid dist DEDICATED_SERVER',
             'mixin', 'side-configuration'),
            ('MixinApplyError: Cannot load class net.minecraft.client.MinecraftClient in environment type SERVER',
             'mixin', 'side-configuration'),
        ]
        params = StdioServerParameters(command=sys.executable,
                                       args=['-m', 'minecode_runtime', '--project', str(self.root)])
        async with Client(params) as client:
            for output, category, subtype in cases:
                for tool in ('analyze_build_failure', 'analyze_runtime_failure'):
                    with self.subTest(tool=tool, output=output):
                        response = await client.call_tool('minecode.' + tool, {'output': output, 'environment': environment})
                        self.assertFalse(response.is_error)
                        data = response.structured_content
                        self.assertEqual(data['category'], category)
                        self.assertEqual(data['mixin_failure'], subtype)
                        self.assertEqual(data['environment']['side'], 'dedicated-server')
                        if category == 'unknown':
                            self.assertEqual(data['confidence'], 'unknown')
                            self.assertEqual(data['evidence'], [])
                        if subtype == 'target-not-found':
                            self.assertEqual(data['mixin_details']['target_member'], 'missingLoadLevel')
                            self.assertTrue(any('missingLoadLevel' in e for e in data['evidence']))
                            self.assertFalse(any('Environment: DEDICATED_SERVER' in e for e in data['evidence']))
                        if category != 'unknown':
                            self.assertTrue(data['evidence'])

    async def test_compact_profile_and_text_preserve_schema_and_expanded_provenance(self):
        self.fabric()
        for i in range(8):
            archive = (self.root / '.gradle/loom-cache/minecraftMaven/net/minecraft'
                       / f'minecraft-merged-{i}/1.21.5+build.1/source-sources.jar')
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('example/Contract.java', 'class Contract {\n void contractProbe() {}\n}')
        with patch.dict(os.environ, {'GRADLE_USER_HOME': str(self.root / 'empty-cache')}):
            async with Client(create_server(Runtime(self.root))) as client:
                tools = {t.name: t for t in (await client.list_tools()).tools}

                async def checked(name, arguments):
                    result = await client.call_tool('minecode.' + name, arguments)
                    self.assertFalse(result.is_error)
                    Draft202012Validator(tools['minecode.' + name].output_schema).validate(result.structured_content)
                    self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                    self.assertNotIn('\n', result.content[0].text)
                    return result.structured_content

                small = await checked('get_project_profile', {})
                full = await checked('get_project_profile', {'include_artifacts': True})
                self.assertFalse(small['local_reference_inventory_included'])
                self.assertEqual(small['local_reference_artifacts'], [])
                self.assertEqual(small['local_reference_artifact_counts'], {'minecraft-sources': 8})
                self.assertTrue(full['local_reference_inventory_included'])
                self.assertEqual(len(full['local_reference_artifacts']), 8)
                for key in ('minecraft_version', 'mappings_version', 'fabric_api_version', 'evidence', 'warnings',
                            'local_reference_limitations'):
                    self.assertEqual(small[key], full[key])
                self.assertLess(len(json.dumps(small)), len(json.dumps(full)) // 2)
                found = await checked('search_reference_code', {'query': 'Contract contractProbe', 'max_results': 1})
                hit = found['results'][0]
                self.assertTrue(hit['untrusted'])
                self.assertNotIn('project_environment', hit['provenance'])
                self.assertIn('artifact_identity', hit['provenance'])
                self.assertIn('identity_evidence', hit['provenance'])
                context = await checked('get_reference_context', {'result_id': hit['result_id'], 'context_lines': 0})
                expanded = context['results'][0]
                self.assertEqual(expanded['revision'], hit['revision'])
                self.assertEqual(expanded['provenance']['archive_revision'], hit['revision'])
                self.assertIn('project_environment', expanded['provenance'])
                self.assertEqual(expanded['excerpt'], hit['excerpt'])

    async def test_tools_schema_and_calls(self):
        self.fabric()
        archive = self.root / '.gradle/loom-cache/minecraftMaven/net/minecraft/minecraft-merged-fixture/1.21.5+build.1/fixture-sources.jar'
        archive.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive, 'w') as output:
            output.writestr('example/Contract.java', 'class Contract { void contractProbe() {} }')
        async with Client(create_server(Runtime(self.root))) as client:
            listed = await client.list_tools()
            expected = {"detect_project", "get_project_profile", "run_gradle", "build_project", "run_client", "analyze_build_failure", "search_sources", "search_reference_code", "get_reference_context", "search_developer_knowledge"}
            expected |= {"provider_status", "call_provider", "analyze_runtime_failure", "search_gameplay_techniques"}
            self.assertEqual({t.name for t in listed.tools}, {"minecode." + n for n in expected})
            for tool in listed.tools:
                Draft202012Validator.check_schema(tool.input_schema)
                Draft202012Validator.check_schema(tool.output_schema)
            calls = [("detect_project", {}), ("get_project_profile", {}),
                                    ("run_gradle", {"task": "build"}), ("build_project", {}),
                                    ("run_client", {}), ("analyze_build_failure", {"output": "Compilation failed"}),
                                    ("search_gameplay_techniques", {"query": "IPC"}),
                                    ("analyze_runtime_failure", {"output": "java.lang.IllegalStateException: contract"}),
                                    ("search_sources", {"query": "Fabric rendering"}),
                                    ("search_reference_code", {"query": "contractProbe"}),
                                    ("search_developer_knowledge", {"query": "callback", "fetch_content": False}),
                                    ("provider_status", {"provider": "minecraft-dev-mcp"}),
                                    ("call_provider", {"capability": "mapping_lookup", "arguments": {}})]
            called = set()
            for name, arguments in calls:
                called.add(name)
                tool = next(t for t in listed.tools if t.name == "minecode." + name)
                Draft202012Validator(tool.input_schema).validate(arguments)
                result = await client.call_tool("minecode." + name, arguments)
                self.assertFalse(result.is_error)
                Draft202012Validator(tool.output_schema).validate(result.structured_content)
                if name == 'search_reference_code':
                    key = result.structured_content['results'][0]['result_id']
            context = await client.call_tool('minecode.get_reference_context', {'result_id': key})
            self.assertFalse(context.is_error)
            tool = next(t for t in listed.tools if t.name == 'minecode.get_reference_context')
            Draft202012Validator(tool.input_schema).validate({'result_id': key})
            Draft202012Validator(tool.output_schema).validate(context.structured_content)
            called.add('get_reference_context')
            self.assertEqual(called, expected)
            contextual = await client.call_tool("minecode.analyze_build_failure", {
                "output": "Project requires Java 21; currently using Java 17",
                "environment": {"minecraft": "1.21.4", "mappings": "yarn-1.21.4+build.8"},
            })
            self.assertFalse(contextual.is_error)
            self.assertEqual(contextual.structured_content["migration_layer"], "build-toolchain")
            self.assertEqual(contextual.structured_content["environment"]["minecraft"], "1.21.4")
            invalid = await client.call_tool("minecode.run_gradle", {"task": "build & echo hi"})
            self.assertTrue(invalid.is_error)

    async def test_actual_stdio_transport(self):
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "minecode_runtime", "--project", str(self.root)])
        async with Client(params) as client:
            result = await client.call_tool("minecode.detect_project")
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["project_root"], str(self.root.resolve()))


class HardeningDiagnosisTests(unittest.TestCase):
    def test_observed_missing_payload_codec(self):
        result = analyze('Caused by: java.lang.IllegalArgumentException: Cannot register handler as no payload type has been registered with name "server_greeting:server_greeting" for CLIENTBOUND PLAY')
        self.assertEqual(result.category, 'networking-registration')
        self.assertEqual(result.networking_failure, 'payload-registration')
        self.assertEqual(result.networking_details, {
            'payload_id': 'server_greeting:server_greeting',
            'direction': 'S2C',
            'phase': 'play',
        })
        self.assertIn('before', result.next_step)
        self.assertTrue(result.evidence)

    def test_explicit_networking_lifecycle_preserves_phase_and_api(self):
        result = analyze(
            'ClientConfigurationNetworking.registerReceiver: '
            'java.lang.IllegalStateException: Cannot register receiver while not configuring!')
        self.assertEqual(result.category, 'networking-registration')
        self.assertEqual(result.networking_failure, 'lifecycle-phase')
        self.assertEqual(result.networking_details, {
            'phase': 'configuration',
            'receiver_api': 'ClientConfigurationNetworking.registerReceiver',
        })

    def test_fabric_networking_symbol_uses_existing_migration_diagnosis(self):
        result = analyze(
            '/project/src/client/java/example/ClientInit.java:22: error: package '
            'net.fabricmc.fabric.api.client.networking.v1 does not exist\n'
            'import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;')
        self.assertEqual((result.category, result.migration_layer),
                         ('fabric-api', 'fabric-loader-api'))
        self.assertIsNone(result.networking_failure)

    def test_build_success_does_not_hide_mixin_crash(self):
        result = analyze('InvalidInjectionException: @Inject annotation on init could not find any targets matching missingLoadLevel\nBUILD SUCCESSFUL in 27s')
        self.assertEqual(result.category, 'mixin')

    def test_unrelated_illegal_argument_is_not_networking(self):
        self.assertEqual(analyze('IllegalArgumentException: width must be positive').category, 'unknown')

    def test_vague_netty_disconnect_is_not_networking_diagnosis(self):
        result = analyze('io.netty.handler.codec.DecoderException: disconnected')
        self.assertEqual(result.category, 'unknown')
        self.assertIsNone(result.networking_failure)
