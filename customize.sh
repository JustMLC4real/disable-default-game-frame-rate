#!/system/bin/sh

[ "$BOOTMODE" = true ] || abort "Install through the Magisk app."

# An absent temporary property is normal after reboot, including at install time.
# Its presence alone cannot prove firmware support either.
case "$(getprop debug.graphics.game_default_frame_rate.disabled)" in
    true|false|1|0) ;;
    '') ui_print "Property currently absent; firmware support must be checked after reboot." ;;
    *) abort "Unrecognized property value; refusing to overwrite it." ;;
esac

set_perm "$MODPATH/service.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
ui_print "Reapplies the property after boot; does not verify actual game FPS."
ui_print "Disable/remove in Magisk and reboot to stop applying it."
