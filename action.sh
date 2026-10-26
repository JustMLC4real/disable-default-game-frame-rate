#!/system/bin/sh

MODDIR=${0%/*}
if [ -f "$MODDIR/status.log" ]; then
    cat "$MODDIR/status.log"
else
    echo "No boot log: the service has not run or could not create its log."
    echo "Check that this module is enabled and reboot after installation."
fi
printf '\nCurrent property: %s\n' "$(getprop debug.graphics.game_default_frame_rate.disabled)"
echo "This confirms property state only. Check the developer toggle and game manually."
