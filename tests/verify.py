"""Host checks with mocked Android commands; these do not replace device tests."""
import os
import sys
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if os.name == "nt":
    BASH = r"C:\Program Files\Git\bin\bash.exe"
MODULE = ROOT

for script in MODULE.glob("*.sh"):
    subprocess.run([BASH, "-n", script.as_posix()], check=True)

MOCK = r'''
getprop() {
    case "$1" in
        sys.boot_completed)
            if [ "$MODE" = timeout ]; then echo 0
            elif [ "$MODE" = delayed ] || [ "$MODE" = disable_wait ] || [ "$MODE" = remove_wait ]; then
                [ "$(cat "$TEST_DIR/sleeps")" -ge 3 ] && echo 1 || echo 0
            else echo 1; fi ;;
        debug.graphics.game_default_frame_rate.disabled) cat "$TEST_DIR/property" ;;
        *) echo "Unexpected property read: $1" >> "$TEST_DIR/unexpected"; return 1 ;;
    esac
}
setprop() {
    printf '%s=%s\n' "$1" "$2" >> "$TEST_DIR/writes"
    [ "$MODE" = reject ] && return 1
    if [ "$MODE" = numeric ]; then printf 1 > "$TEST_DIR/property"
    elif [ "$MODE" != mismatch ]; then printf '%s' "$2" > "$TEST_DIR/property"; fi
    return 0
}
settings() { echo "$*" >> "$TEST_DIR/unexpected"; return 1; }
sleep() {
    count=$(cat "$TEST_DIR/sleeps")
    printf '%s' "$((count + 1))" > "$TEST_DIR/sleeps"
    [ "$MODE" = disable_wait ] && touch "$TEST_DIR/disable"
    [ "$MODE" = remove_wait ] && touch "$TEST_DIR/remove"
    return 0
}
export -f getprop setprop sleep settings
bash "$TEST_DIR/service.sh"
'''

cases = [
    ("normal", "false", None, 0, "Property applied", True),
    ("normal", "0", None, 0, "Property applied", True),
    ("normal", "true", None, 0, "Property applied", True),
    ("normal", "1", None, 0, "Property applied", True),
    ("normal", "", None, 0, "Property applied", True),
    ("normal", "unexpected", None, 1, "unrecognized property", False),
    ("reject", "false", None, 1, "rejected", True),
    ("mismatch", "false", None, 1, "did not confirm", True),
    ("timeout", "false", None, 1, "180 seconds", False),
    ("normal", "false", "disable", 0, "", False),
    ("normal", "false", "remove", 0, "", False),
    ("delayed", "false", None, 0, "Property applied", True),
    ("disable_wait", "false", None, 0, "", False),
    ("remove_wait", "false", None, 0, "", False),
    ("numeric", "false", None, 0, "Property applied", True),
]
for mode, value, flag, expected_rc, message, writes in cases:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        shutil.copy(MODULE / "service.sh", path)
        (path / "property").write_text(value)
        (path / "sleeps").write_text("0")
        if flag:
            (path / flag).touch()
        env = {**os.environ, "MODE": mode, "TEST_DIR": path.as_posix()}
        result = subprocess.run([BASH, "-c", MOCK], env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == expected_rc, (mode, result.stderr)
        assert message in (path / "status.log").read_text(), mode
        assert (path / "writes").exists() == writes, mode
        assert not (path / "unexpected").exists(), mode
        if mode == "timeout":
            assert (path / "sleeps").read_text() == "180"
        elif mode in ("delayed", "disable_wait", "remove_wait"):
            assert (path / "sleeps").read_text() == "3"
        if writes:
            assert (path / "writes").read_text() == (
                "debug.graphics.game_default_frame_rate.disabled=true\n"
            )

INSTALL_MOCK = r'''
getprop() { printf '%s' "$TEST_VALUE"; }
ui_print() { printf '%s\n' "$*"; }
abort() { printf '%s\n' "$*"; exit 1; }
set_perm() { printf 'PERM:%s:%s:%s:%s\n' "$1" "$2" "$3" "$4"; }
BOOTMODE="$TEST_BOOTMODE"
MODPATH="$TEST_MODULE"
. "$TEST_MODULE/customize.sh"
'''
for value, bootmode, expected_rc in [
    ("", "true", 0), ("false", "true", 0), ("true", "true", 0),
    ("0", "true", 0), ("1", "true", 0),
    ("unexpected", "true", 1), ("false", "false", 1),
]:
    env = {**os.environ, "TEST_VALUE": value, "TEST_BOOTMODE": bootmode,
           "TEST_MODULE": MODULE.as_posix()}
    result = subprocess.run([BASH, "-c", INSTALL_MOCK], env=env,
                            capture_output=True, text=True)
    assert result.returncode == expected_rc, (value, bootmode, result.stdout, result.stderr)
    if expected_rc == 0:
        for script in ("service.sh", "action.sh"):
            assert f"PERM:{MODULE.as_posix()}/{script}:0:0:0755" in result.stdout
    else:
        assert "PERM:" not in result.stdout

ACTION_MOCK = r'''
getprop() { cat "$TEST_DIR/property"; }
export -f getprop
bash "$TEST_DIR/action.sh"
'''
for logged, current in [(False, ""), (True, "true"), (True, "false")]:
    with tempfile.TemporaryDirectory(prefix="fps action ") as directory:
        path = Path(directory)
        shutil.copy(MODULE / "action.sh", path)
        (path / "property").write_text(current)
        if logged:
            (path / "status.log").write_text("Property applied earlier.\n")
        env = {**os.environ, "TEST_DIR": path.as_posix()}
        result = subprocess.run([BASH, "-c", ACTION_MOCK], env=env,
                                capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert f"Current property: {current}\n" in result.stdout
        assert ("Property applied earlier." if logged else "No boot log") in result.stdout
        assert "property state only" in result.stdout

# Optionally pass the release ZIP as the first argument.
if len(sys.argv) > 1:
    with zipfile.ZipFile(sys.argv[1]) as package:
        expected = {"module.prop", "service.sh", "customize.sh", "action.sh",
                    "skip_mount", "LICENSE", "README.md"}
        assert set(package.namelist()) == expected
        assert package.testzip() is None
        for name in expected:
            data = package.read(name)
            assert not data.startswith(b"\xef\xbb\xbf"), name
            assert b"\r" not in data, name
            assert data == (MODULE / name).read_bytes().replace(b"\r\n", b"\n"), name
    print("PASS: release ZIP integrity, contents, encoding and source match.")

metadata = dict(line.split("=", 1) for line in
                (MODULE / "module.prop").read_text().splitlines())
assert metadata["id"] == "disable_default_game_frame_rate"
assert metadata["version"] == "1.0"
assert metadata["author"] == "JustMLC"

# The module never reads or enables developer settings. This is a source check,
# not a simulation of Motorola's implementation or Android's system services.
service = (MODULE / "service.sh").read_text()
assert "development_settings_enabled" not in service
assert "settings put" not in service
assert not (MODULE / "system.prop").exists()
assert not (MODULE / "post-fs-data.sh").exists()
assert not (MODULE / "sepolicy.rule").exists()
print(f"PASS: shell syntax, {len(cases)} boot scenarios, 7 install scenarios, "
      "3 diagnostic scenarios, permissions, bounded waits and module metadata.")
