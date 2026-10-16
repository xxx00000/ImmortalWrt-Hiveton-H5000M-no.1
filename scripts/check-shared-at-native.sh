#!/bin/sh
# Linux CI gate: real ubusd + libubus + patched daemon/CLI + Python Web client.
# Prerequisites: build-essential cmake pkg-config libjson-c-dev git python3.
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source=${1:?usage: check-shared-at-native.sh /path/to/patched/qmodem-source}
source=$(CDPATH= cd -- "$source" && pwd)
[ "$(uname -s)" = Linux ] || { echo 'Native libubus integration requires Linux' >&2; exit 1; }
cache=${SHARED_AT_NATIVE_DIR:-"$repo/work/shared-at-native"}
mkdir -p "$cache"
cache=$(CDPATH= cd -- "$cache" && pwd)
prefix="$cache/install"
fetch() {
    project=$1 revision=$2
    if [ ! -d "$cache/$project/.git" ]; then git init -q "$cache/$project"; fi
    if ! git -C "$cache/$project" cat-file -e "$revision^{commit}" 2>/dev/null; then
        git -C "$cache/$project" fetch --depth 1 "https://github.com/openwrt/$project.git" "$revision"
    fi
    git -C "$cache/$project" checkout --detach "$revision"
    [ "$(git -C "$cache/$project" rev-parse HEAD)" = "$revision" ]
}
fetch libubox da2d205a5cf3e877c45a2eec488218cbaf452e7d
fetch ubus 414c60a2e29e72c2c4f573bc50ad54aef076d169
cmake -S "$cache/libubox" -B "$cache/libubox-build" -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DCMAKE_INSTALL_PREFIX="$prefix"
cmake --build "$cache/libubox-build" -j2
cmake --install "$cache/libubox-build"
cmake -S "$cache/ubus" -B "$cache/ubus-build" -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DCMAKE_PREFIX_PATH="$prefix" -DCMAKE_INSTALL_PREFIX="$prefix"
cmake --build "$cache/ubus-build" -j2
cmake --install "$cache/ubus-build"
export PATH="$prefix/bin:$prefix/sbin:$PATH"
export LD_LIBRARY_PATH="$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$cache/bin"
cc -O2 -g -Wall -Wextra -std=gnu99 -D_GNU_SOURCE -I"$prefix/include" \
    "$source"/application/ubus_at_daemon/src/*.c \
    -L"$prefix/lib" -lubus -lubox -lblobmsg_json -ljson-c -pthread -o "$cache/bin/ubus-at-daemon"
cc -O2 -g -Wall -Wextra -std=gnu99 -D_GNU_SOURCE -DENABLE_UBUS_DAEMON -I"$prefix/include" \
    "$source"/application/tom_modem/src/main.c "$source"/application/tom_modem/src/utils.c \
    "$source"/application/tom_modem/src/operations.c "$source"/application/tom_modem/src/transport.c \
    "$source"/application/tom_modem/src/ubus_client.c "$source"/application/tom_modem/src/extlib/pdu.c \
    "$source"/application/tom_modem/src/extlib/ucs2_to_utf8.c \
    -L"$prefix/lib" -lubus -lubox -lblobmsg_json -ljson-c -o "$cache/bin/tom_modem"
make -C "$source/application/ubus_at_daemon/tests" clean all
cc -O1 -g -std=gnu99 -ffunction-sections -fdata-sections \
    -I"$source/application/tom_modem/src" \
    "$source/application/tom_modem/tests/test_sms_transaction.c" \
    "$source/application/tom_modem/src/operations.c" -Wl,--gc-sections -o "$cache/bin/test_sms_transaction"
"$cache/bin/test_sms_transaction"
# OpenWrt runs this service as root. A non-root ubusd peer without a
# root-owned ACL cannot publish/call at-daemon; keep only the harness privileged.
if [ "$(id -u)" = 0 ]; then
    python3 "$repo/tests/native_shared_at.py" --daemon "$cache/bin/ubus-at-daemon" \
        --cli "$cache/bin/tom_modem" --web "$repo/files/usr/lib/at-webserver/shared_at.py"
else
    command -v sudo >/dev/null || { echo 'Native ubus harness requires root or non-interactive sudo' >&2; exit 1; }
    sudo -n env "PATH=$PATH" "LD_LIBRARY_PATH=$LD_LIBRARY_PATH" \
        python3 "$repo/tests/native_shared_at.py" --daemon "$cache/bin/ubus-at-daemon" \
        --cli "$cache/bin/tom_modem" --web "$repo/files/usr/lib/at-webserver/shared_at.py"
fi
