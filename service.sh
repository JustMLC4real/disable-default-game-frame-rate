#!/system/bin/sh

MODDIR=${0%/*}
exec > "$MODDIR/status.log" 2>&1
PROP=debug.graphics.game_default_frame_rate.disabled
echo "Disable Default Game Frame Rate 1.0 - boot service started."

# Bound the wait; this late_start script does not block Android boot.
attempt=0
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    if [ "$attempt" -ge 180 ]; then
        echo "Not applied: boot did not complete within 180 seconds."
        exit 1
    fi
    sleep 1
    attempt=$((attempt + 1))
done

# Respect disabling/removing the module while this script was waiting.
[ -f "$MODDIR/disable" ] && exit 0
[ -f "$MODDIR/remove" ] && exit 0

case "$(getprop "$PROP")" in
    ''|true|false|1|0) ;;
    *) echo "Not applied: unrecognized property value on this boot."; exit 1 ;;
esac

# This temporary debug property can be absent after reboot. A successful write
# does not establish that this firmware uses it; check the toggle manually.
printf 'Before write: [%s]\n' "$(getprop "$PROP")"
if ! setprop "$PROP" true; then
    echo "Failed: Android rejected the property write."
    exit 1
fi
case "$(getprop "$PROP")" in
    true|1) echo "Property applied. Check the developer toggle and game manually; game FPS is not verified." ;;
    *) echo "Failed: property readback did not confirm the write."; exit 1 ;;
esac
