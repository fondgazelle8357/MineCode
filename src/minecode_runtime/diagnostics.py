"""Pattern-based hypotheses, not an AI backend or authoritative root-cause engine."""
import re
from .models import Diagnosis, FailureEnvironment

MAX_LOG_LINE = 2048


def bounded_log(text: str) -> tuple[str, bool]:
    """Omit oversized lines before regex processing, retaining original line numbers."""
    lines = text.splitlines()
    truncated = any(len(line) > MAX_LOG_LINE for line in lines)
    if not truncated:
        return text, False
    # Do not keep a tail or prefix that could separate a secret from its label.
    return "\n".join(line if len(line) <= MAX_LOG_LINE else "[oversized log line omitted]"
                     for line in lines), True

RULES = [
    ("networking-registration", r"Cannot register handler as no payload type has been registered|Cannot register receiver while not (?:in game|configuring)",
     "Fabric networking reported an explicit payload or receiver registration failure.", "Verify the active-version payload registry, direction, phase, side and receiver lifecycle."),
    ("java-version", r"Unsupported class file major version|invalid (?:source|target) release|release version .+ not supported|requires Java|requires at least JVM runtime version|UnsupportedClassVersionError|class file version",
     "The Java compiler or Gradle JVM may not match the required Java version.", "Inspect the declared toolchain and the JVM used by the wrapper; align their versions."),
    ("gradle-version", r"minimum supported Gradle version is|requires Gradle(?: version)?|Gradle [\d.]+ is required|incompatible with (?:this version of )?Gradle",
     "The Gradle wrapper may not satisfy a plugin or build requirement.", "Compare the wrapper version with the reported plugin requirement before changing project source."),
    ("mixin", r"MixinApplyError|InvalidMixinException|InjectionError|InvalidInjectionException|MixinTransformerError",
     "A Mixin target, injection, or configuration may not match this environment.", "Inspect the named Mixin and target signature against this Minecraft version, mappings, and side."),
    ("side-source-set", r"Cannot load class .+ in environment|is only available in environment (?:CLIENT|SERVER)|invalid dist|wrong (?:logical|physical) side|attempted to load class .+ for invalid dist",
     "The log explicitly reports an environment or side reachability mismatch.", "Confirm the failing source set and entrypoint, then keep client-only classes unreachable from common or dedicated-server initialization."),
    ("dependency", r"Could not resolve|Could not find [\w.-]+:[\w.-]+|Could not GET|Could not download",
     "Gradle could not resolve a dependency or download.", "Check the named coordinate, repositories, cached dependencies, and explicit network permission."),
    ("symbol-unavailable", r"cannot find symbol|unresolved reference|NoSuchMethodError|NoSuchFieldError|ClassNotFoundException|NoClassDefFoundError|package .+ does not exist",
     "A referenced symbol is unavailable, but the responsible compatibility layer is not established yet.", "Inspect the preserved symbol, namespace, classpath, and active versions before choosing a replacement."),
    ("compiler", r"\.java:\d+: error:|Compilation failed|incompatible types|';' expected",
     "Java compilation failed.", "Inspect the first compiler error in the affected file before addressing follow-on errors."),
    ("gradle-configuration", r"Could not (?:compile|evaluate)|Plugin .+ was not found|Task .+ not found|A problem occurred (?:evaluating|configuring)|Could not set unknown property",
     "Gradle configuration, plugin resolution, or task selection failed.", "Inspect the reported build file/plugin/task and its compatibility with the wrapper version."),
]


MIGRATION_LAYERS = {
    "networking-registration": "fabric-loader-api",
    "java-version": "build-toolchain",
    "gradle-version": "build-toolchain",
    "mixin": "mixin",
    "side-source-set": "side-source-set",
    "dependency": "build-toolchain",
    "gradle-configuration": "build-toolchain",
    "compiler": "ordinary-java",
}


MIXIN_FAILURE_RULES = [
    ("mappings-remap",
     r"(?:ref(?:erence )?map|remap|obfuscation mapping).*(?:could not|failed|missing|not found|unable)|"
     r"(?:could not|failed|unable)\s+(?:to\s+)?(?:read|load|find|resolve|locate)\s+"
     r"(?:(?:the|a|an)\s+)?(?:ref(?:erence )?map|obfuscation mapping)",
     "Mixin reported an explicit refmap, remapping, or obfuscation-mapping failure.",
     "Confirm the active mappings namespace and the Mixin remap/refmap configuration before changing any target name."),
    ("side-configuration",
     r"invalid dist|Cannot load class .+ in environment|is only available in environment (?:CLIENT|SERVER)|"
     r"wrong (?:logical|physical) side|"
     r"mixin config(?:uration)?.*(?:could not|failed|missing|not found)|"
     r"(?:could not|failed) to load mixin config(?:uration)?",
     "Mixin or its target is unavailable because the log explicitly reports a side or configuration-loading problem.",
     "Confirm the Mixin config is registered and applies on this side, then verify client-only target reachability."),
    ("descriptor-handler-mismatch",
     r"invalid (?:handler |callback |method )?(?:descriptor|signature)|"
     r"(?:descriptor|signature).*(?:does not match|mismatch|incompatible)|"
     r"expected\s*:?\s*\([^\r\n]*\).*(?:found|actual)\s*:?\s*\(",
     "A target, overload, or injector handler descriptor does not match the shape Mixin expected.",
     "Compare the exact current target descriptor and overload first, then validate the handler arguments, return type, and callback type."),
    ("injection-point-mismatch",
     r"failed injection check|\(0/\d+\) succeeded|"
     r"(?:required|expected) \d+ (?:injection|invocation).*(?:0|none) (?:succeeded|matched|found)|"
     r"could not find (?:any )?(?:valid )?injection points?|no matching (?:instructions|insns)|"
     r"@At[^\r\n]*(?:could not|failed|matched 0)",
     "The injector did not satisfy its injection-point or required-count constraint; the target bytecode shape may have changed.",
     "After confirming the target method descriptor, inspect its current bytecode for the @At target, ordinal, slice, and required count."),
    ("target-not-found",
     r"could not find any targets matching|no candidates were found matching|"
     r"could not find target (?:class|method|field)|"
     r"(?:@Mixin target|target (?:class|method|field))[^\r\n]*(?:was )?not found|"
     r"unable to locate (?:target )?(?:class|method|field)",
     "The Mixin selector matched no target class or member in this environment; the log does not prove whether it was renamed, removed, remapped, or loaded on another side.",
     "Confirm the project Minecraft version, mappings, and side; inspect the local selector and the current-version target class, member, and descriptor before renaming anything."),
]


def _first(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)[:500]
    return None


def _compiler_details(clean: str) -> dict[str, str]:
    details: dict[str, str] = {}
    compiler = re.search(r"(?m)^(.+\.java):(\d+):\s*error:\s*(.+)$", clean)
    scope = clean
    if compiler:
        following = clean[compiler.start():]
        next_error = re.search(r"(?m)^.+\.java:\d+:\s*error:", following[compiler.end() - compiler.start():])
        end = compiler.end() - compiler.start() + next_error.start() if next_error else len(following)
        scope = following[:min(end, 4000)]
    package = re.search(r"\bpackage\s+([\w.]+)\s+does not exist", scope, re.I)
    imported = re.search(r"(?m)^\s*import\s+(?:static\s+)?([\w.$*]+)\s*;", scope)
    symbol = re.search(r"(?m)^\s*symbol:\s*(class|interface|enum|record|method|variable)\s+([^\r\n]+)", scope, re.I)
    location = re.search(r"(?m)^\s*location:\s*(?:class|interface|package)\s+([^\r\n]+)", scope, re.I)
    missing_class = re.search(r"(?:ClassNotFoundException|NoClassDefFoundError):\s*([\w.$/]+)", clean)
    missing_method = re.search(
        r"NoSuchMethodError:[^\r\n]*?([\w$/]+(?:\.[\w$]+)+)\.([A-Za-z_$<>][\w$<>]*)"
        r"(\([^()\r\n]*\)[^\s'\r\n]*)",
        clean,
    )
    missing_field = re.search(
        r"NoSuchFieldError:[^\r\n]*?([\w$/]+(?:\.[\w$]+)+)\.([A-Za-z_$<>][\w$<>]*)",
        clean,
    )
    missing_member = missing_method or missing_field
    if compiler:
        details["source_file"] = compiler.group(1)[-500:]
        details["source_line"] = compiler.group(2)
    if package:
        details["package"] = package.group(1)[:500]
        details.setdefault("symbol_kind", "package")
        details.setdefault("unresolved_symbol", package.group(1)[:500])
    if imported:
        details["import"] = imported.group(1)[:500]
    if symbol:
        details["symbol_kind"] = symbol.group(1).lower()
        details["unresolved_symbol"] = symbol.group(2).strip()[:500]
    if location:
        details["location"] = location.group(1).strip()[:500]
    if missing_class:
        details["symbol_kind"] = "class"
        details["unresolved_symbol"] = missing_class.group(1).replace("/", ".")[:500]
    if missing_member:
        owner, member = missing_member.group(1), missing_member.group(2)
        suffix = missing_member.group(3) if missing_method else ""
        details["symbol_kind"] = "method" if missing_method else "field"
        details["owner"] = owner.replace("/", ".")[:500]
        details["unresolved_symbol"] = (member + suffix).strip()[:500]
    return details


def _symbol_diagnosis(clean: str, environment: FailureEnvironment) -> tuple[str, str, str, str, dict[str, str], list[str]]:
    details = _compiler_details(clean)
    reference = " ".join(details.get(key, "") for key in ("package", "import", "location", "owner", "unresolved_symbol"))
    side = (environment.side or "").lower()
    client_reference = "net.minecraft.client" in reference or "net.fabricmc.fabric.api.client" in reference
    if client_reference and side in {"server", "dedicated-server", "dedicated_server"}:
        category, layer = "side-source-set", "side-source-set"
        cause = "A reported server environment is compiling or loading an explicitly client-only namespace."
        step = "Confirm the source set and entrypoint that reaches this symbol; keep the client reference out of common and dedicated-server paths."
    elif "net.fabricmc." in reference:
        category, layer = "fabric-api", "fabric-loader-api"
        cause = "The unavailable symbol is in a Fabric or Fabric Loader namespace, making an API, dependency, or version mismatch more likely."
        step = "Confirm the target Fabric API/Loader version and use its exact-version primary documentation before changing the call or import."
    elif "net.minecraft." in reference or "com.mojang.blaze3d." in reference:
        category, layer = "minecraft-symbol", "mappings-vanilla"
        cause = "The unavailable symbol is in a Minecraft namespace; its current name, package, signature, classpath, or mappings may differ."
        step = "Confirm the active mappings namespace, then inspect current-version Minecraft source or mappings for this exact symbol before replacing it."
    elif details.get("source_file"):
        category, layer = "compiler", "ordinary-java"
        cause = "Java could not resolve the preserved symbol, but the log does not establish a Minecraft mappings or Fabric API migration."
        step = "Inspect the declaration, import, spelling, and compile classpath for this symbol before treating it as a version migration."
    else:
        category, layer = "symbol-unavailable", "unknown"
        cause = "A runtime symbol is unavailable, but the log does not establish whether Minecraft, Fabric, another dependency, or project code owns it."
        step = "Identify the preserved owner and resolved runtime dependency before treating this as a Minecraft version migration."
    evidence_pattern = re.compile(
        r"\.java:\d+:\s*error:|cannot find symbol|unresolved reference|^\s*(?:symbol|location):|"
        r"^\s*import\s+|package .+ does not exist|NoSuch(?:Method|Field)Error|ClassNotFoundException|NoClassDefFoundError",
        re.I,
    )
    evidence = [line.strip() for line in clean.splitlines() if evidence_pattern.search(line)][:6]
    return category, layer, cause, step, details, evidence


def _reported_context(environment: FailureEnvironment) -> str:
    labels = {
        "minecraft": "minecraft",
        "loader": "loader",
        "fabric_api": "fabric_api",
        "loom": "loom",
        "mappings": "mappings",
        "side": "side",
        "java": "java",
        "gradle": "gradle",
        "dependency": "dependency",
    }
    values = environment.model_dump()
    return ", ".join(f"{label} {values[key]}" for key, label in labels.items() if values[key])


def _mixin_diagnosis(clean: str, lines: list[str]) -> tuple[str, str, str, dict[str, str], list[str]]:
    subtype = "unclassified"
    cause = "Mixin failed, but this log does not distinguish a target, descriptor, injection-point, mappings, or side/configuration failure."
    step = ("Identify the Mixin selector, exact Minecraft version, mappings, and side; then verify the current target descriptor "
            "and injection point before editing the annotation or handler.")
    for candidate, pattern, hypothesis, next_step in MIXIN_FAILURE_RULES:
        if re.search(pattern, clean, re.I):
            subtype, cause, step = candidate, hypothesis, next_step
            break

    details: dict[str, str] = {}
    simple = {
        "mixin": _first((r"\[\w[\w.-]*\.json:([\w.$/]+)",
                         r"(?:mixin class|in mixin)\s+['\"]?([\w.$/]+)",
                         r"\b([\w.$/]*[A-Z][\w$]*Mixin)\b"), clean),
        "target_class": _first((r"(?:@Mixin target|target class)\s+['\"]?([\w.$/]+)",
                                 r"(?:targets? matching|no candidates were found matching)[^\r\n]*\bin\s+([\w.$/]+)",
                                 r"\bin target\s+['\"]?([\w.$/]+)"), clean),
        "config": _first((r"\[([\w.-]+\.json):",
                          r"(?:config(?:uration)?|from)\s+[\[('\"]*([\w.-]+\.json)"), clean),
        "injector": _first((r"(@(?:Inject|Redirect|ModifyArg|ModifyVariable|ModifyConstant|ModifyExpressionValue|WrapOperation))\b",), clean),
        "handler": _first((r"(?:annotation on|handler method)\s+['\"]?([A-Za-z_$<>][\w$<>]*)",), clean),
        "injection_point": _first((r"@At\(\s*(?:value\s*=\s*)?['\"]?([A-Z_]+)",), clean),
        "at_target": _first((r"@At\([^\r\n]*?target\s*=\s*['\"]([^'\"]+)",), clean),
        "ordinal": _first((r"\bordinal\s*=\s*(\d+)",), clean),
        "expected_descriptor": _first((r"\bExpected(?: descriptor)?\s*:?\s*(\([^()\r\n]{0,500}\)(?:\[*(?:[BCDFIJSZV]|L[\w/$]+;)))",), clean),
        "found_descriptor": _first((r"\b(?:Found|Actual)(?: descriptor)?\s*:?\s*(\([^()\r\n]{0,500}\)(?:\[*(?:[BCDFIJSZV]|L[\w/$]+;)))",), clean),
    }
    details.update({key: value for key, value in simple.items() if value})
    selector = re.search(
        r"(?:targets? matching|target (?:method|field)|selector)\s+['\"`]?"
        r"([A-Za-z_$<>][\w$<>]*)\s*(\([^()\r\n]{0,500}\)(?:\[*(?:[BCDFIJSZV]|L[\w/$]+;)))",
        clean,
        re.I,
    )
    if selector:
        details.setdefault("target_member", selector.group(1)[:500])
        details.setdefault("descriptor", selector.group(2)[:500])
    else:
        member = _first((r"(?:targets? matching|target (?:method|field)|selector)\s+['\"`]?([A-Za-z_$<>][\w$<>]*)",), clean)
        if member:
            details["target_member"] = member
    count = re.search(r"\((\d+)\s*/\s*(\d+)\)\s+succeeded", clean, re.I)
    if count:
        details["found_count"], details["expected_count"] = count.group(1), count.group(2)

    evidence_pattern = re.compile(
        r"Mixin|@(?:Inject|Redirect|ModifyArg|ModifyVariable|ModifyConstant|ModifyExpressionValue|WrapOperation|At)\b|"
        r"injection|target|descriptor|signature|refmap|remap|Cannot load class .+ in environment|invalid dist",
        re.I,
    )
    evidence = [line for line in lines if evidence_pattern.search(line)][:6]
    return subtype, cause, step, details, evidence


def _networking_diagnosis(clean: str, lines: list[str]) -> tuple[str, str, str, dict[str, str], list[str]]:
    if re.search(r"Cannot register handler as no payload type has been registered", clean, re.I):
        subtype = "payload-registration"
        cause = "A receiver was registered before its matching payload type and codec were available for the reported direction and phase."
        step = "Using the active-version Fabric API, register the matching payload type and codec for this direction and phase on both physical sides before registering the receiver on the logical destination."
    else:
        subtype = "lifecycle-phase"
        cause = "A connection-scoped receiver was registered outside the lifecycle phase required by the networking API."
        step = "Use a global receiver during initialization or register the connection receiver from the exact-version play/configuration lifecycle hook, then verify the receiving side."

    details: dict[str, str] = {}
    payload_id = _first((r'payload type has been registered with name ["\']([^"\']+)',), clean)
    if payload_id:
        details["payload_id"] = payload_id
    flow = _first((r"\b(CLIENTBOUND|SERVERBOUND)\b",), clean)
    if flow:
        details["direction"] = "S2C" if flow.upper() == "CLIENTBOUND" else "C2S"
    phase = _first((r"\b(?:CLIENTBOUND|SERVERBOUND)\s+(PLAY|CONFIGURATION)\b",), clean)
    if not phase and re.search(r"not in game", clean, re.I):
        phase = "PLAY"
    elif not phase and re.search(r"not configuring", clean, re.I):
        phase = "CONFIGURATION"
    if phase:
        details["phase"] = phase.lower()
    api = _first((r"\b((?:Client|Server)(?:Play|Configuration)Networking(?:\.(?:registerGlobalReceiver|registerReceiver))?)\b",), clean)
    if api:
        details["receiver_api"] = api

    evidence_pattern = re.compile(
        r"Cannot register handler as no payload type has been registered|"
        r"Cannot register receiver while not (?:in game|configuring)",
        re.I,
    )
    evidence = [line for line in lines if evidence_pattern.search(line)][:6]
    return subtype, cause, step, details, evidence


def analyze(output: str, environment: FailureEnvironment | None = None) -> Diagnosis:
    if len(output) > 128000:
        raise ValueError("Failure output must not exceed 128,000 characters.")
    bounded, input_truncated = bounded_log(output)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", bounded)
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    category, cause, step = "unknown", "The captured output does not establish a root cause.", "Inspect the first exception and its deepest cause; capture a fuller local build log if needed."
    environment = environment or FailureEnvironment()
    evidence = []
    migration_layer = "unknown"
    migration_details: dict[str, str] = {}
    mixin_failure = None
    mixin_details = {}
    networking_failure = None
    networking_details = {}
    for name, pattern, hypothesis, next_step in RULES:
        matches = [line for line in lines if re.search(pattern, line, re.I)]
        if matches:
            category, cause, step, evidence = name, hypothesis, next_step, matches[:3]
            break
    if category == "mixin":
        mixin_failure, cause, step, mixin_details, mixin_evidence = _mixin_diagnosis(clean, lines)
        evidence = mixin_evidence or evidence
    elif category == "networking-registration":
        networking_failure, cause, step, networking_details, networking_evidence = _networking_diagnosis(clean, lines)
        evidence = networking_evidence or evidence
    elif category == "symbol-unavailable":
        category, migration_layer, cause, step, migration_details, symbol_evidence = _symbol_diagnosis(clean, environment)
        evidence = symbol_evidence or evidence
    if migration_layer == "unknown":
        migration_layer = MIGRATION_LAYERS.get(category, "unknown")
    compiler = re.search(r"(?m)^(.+\.java):(\d+):\s*error:\s*(.+)$", clean)
    exception = re.findall(r"\b([\w.$]+(?:Exception|Error))\b(?::[^\n]*)?", clean)
    dependency = re.search(r"(?:Could not resolve|Could not find)\s+([\w.-]+:[\w.-]+:[^\s.]+(?:\.[^\s.]+)*)", clean)
    expected = re.search(r"(?:requires Java|requires at least JVM runtime version|release version|invalid (?:source|target) release:)\s*(\d+)", clean, re.I)
    observed = re.search(r"(?:currently using Java|current (?:Java|JVM)(?: version)?[: ]+|This build uses a Java)\s*(\d+)", clean, re.I)
    if category == "java-version" and expected and observed:
        cause = f"The build requests Java {expected[1]}, but Gradle reports Java {observed[1]}."
        step = f"Run the wrapper with the required Java {expected[1]} JVM; the mod's compilation target can be different."
    context = _reported_context(environment)
    if context:
        step = f"Reported project context: {context}. {step}"
    return Diagnosis(category=category, likely_root_cause=cause, input_truncated=input_truncated,
        environment=environment, migration_layer=migration_layer, migration_details=migration_details,
        mixin_failure=mixin_failure, mixin_details=mixin_details,
        networking_failure=networking_failure, networking_details=networking_details,
        important_error=evidence[0][:1000] if evidence else lines[-1][:1000] if lines else None,
        affected_file=compiler[1] if compiler else None,
        affected_line=int(compiler[2]) if compiler else None,
        affected_class=exception[-1] if exception else None,
        exception_class=exception[-1] if exception else None,
        dependency=dependency[1].rstrip(".") if dependency else None,
        expected_java=expected[1] if expected else None, observed_java=observed[1] if observed else None,
        evidence=[line[:1000] for line in evidence], next_step=step,
        confidence="unknown" if category == "unknown" else "pattern-match")
