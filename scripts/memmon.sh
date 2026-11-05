#!/usr/bin/env bash
# Memory sampler for bench.sh --memmon: every INTERVAL s, appends "t,epoch_ms,rss_mb,anon_mb,file_mb,swap_mb,vram_proc_mb,vram_total_mb"
# for the running iowolfsp process to OUT (CSV). vram_proc_mb is the game's own GPU memory (empty if the driver
# does not list it), vram_total_mb the whole GPU's used memory. epoch_ms is CLOCK_REALTIME in ms (the same clock as the
# engine's profiling/mem_*_timeline.csv rows, so the report can merge them). Runs until killed.
# Usage: scripts/memmon.sh OUT [INTERVAL]
set -u
export LC_ALL=C
OUT="$1"; INTERVAL="${2:-0.5}"
echo "t,epoch_ms,rss_mb,anon_mb,file_mb,swap_mb,vram_proc_mb,vram_total_mb" > "$OUT"
T0=$(date +%s.%N)  # t = seconds since start
while :; do
	pid="$(pgrep -nx iowolfsp.x86_64 || true)"
	if [[ -n "$pid" && -r /proc/$pid/status ]]; then
		now="$(date +%s%3N)"
		read -r rss anon file swap < <(awk '/^VmRSS/{r=$2} /^RssAnon/{a=$2} /^RssFile/{f=$2} /^VmSwap/{s=$2} END{printf "%.1f %.1f %.1f %.1f\n", r/1024, a/1024, f/1024, s/1024}' /proc/$pid/status)
		vp="$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits 2>/dev/null | awk -F', ' -v p="$pid" '$1==p{print $2}')"
		if [[ -z "$vp" ]]; then
			vp="$(nvidia-smi pmon -c 1 -s m 2>/dev/null | awk -v p="$pid" '$2==p{print $4}')"
			[[ "$vp" == "-" ]] && vp=""
		fi
		vt="$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1)"
		printf '%.1f,%s,%s,%s,%s,%s,%s,%s\n' "$(awk -v a="$now" -v b="$T0" 'BEGIN{print a/1000-b}')" "$now" "$rss" "$anon" "$file" "$swap" "$vp" "$vt" >> "$OUT"
	fi
	sleep "$INTERVAL"
done
