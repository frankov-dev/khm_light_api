"""
Parser for power outage schedule text.

Parses schedule blocks into structured data with time intervals.
Handles operational changes (earlier start, extended end, etc.).
"""

import re
from typing import Optional


class Parser:
    """
    Parser for outage schedule text.
    
    Handles:
        - Base schedule: "підчерга 1.1 – з 10:00 до 15:00"
        - Earlier start: "розпочнеться раніше – о 09:00"
        - Extended end: "триватиме довше – до 18:00"
        - Full change: "раніше – об 11:00 і триватиме до 16:00"
        - Extra outage: "додатково буде знеструмлено з 16:00 до 18:00"
    """
    
    # Time interval pattern: "з HH:MM до HH:MM"
    TIME_PATTERN = re.compile(r'з\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})')
    
    def parse_block(self, block: dict) -> dict:
        """
        Parse a schedule block for a specific date.
        
        Args:
            block: {"date": "YYYY-MM-DD", "schedule_text": "...", "extras_text": "..."}
        
        Returns:
            {"date": "...", "queues": {"1.1": [...], ...}, "message": "..."}
        """
        queues = {}
        
        # Parse base schedule
        for line in block.get("schedule_text", "").split("\n"):
            match = re.search(r'підчерга\s+(\d\.\d)', line, re.IGNORECASE)
            if match:
                queue = match.group(1)
                intervals = [
                    {"start": self._normalize_time(s), "end": self._normalize_time(e), "type": "base"}
                    for s, e in self.TIME_PATTERN.findall(line)
                ]
                if intervals:
                    queues[queue] = intervals
        
        # Parse and apply operational changes
        extras_text = block.get("extras_text", "")
        if extras_text:
            self._apply_changes(extras_text, queues)
        
        return {
            "date": block["date"],
            "queues": self._merge_intervals(queues),
            "message": extras_text if extras_text else None
        }
    
    def _normalize_time(self, time_str: str) -> str:
        """Normalize time to HH:MM format (e.g., 7:00 -> 07:00)."""
        parts = time_str.split(":")
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    
    def _apply_changes(self, extras_text: str, queues: dict) -> None:
        """Apply operational changes to queue schedules."""
        text = extras_text.replace("–", "-").replace("—", "-")
        
        # Split into separate entries
        entries = re.split(r'[;.,:]?\s*-\s*(?=у\s+підчерг|підчерг[иуа])', text)
        processed = set()
        
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            
            # Extract queue numbers
            queue_matches = re.findall(r'підчерг[иуа]?\s+([\d\.\s,]+)', entry, re.IGNORECASE)
            queue_nums = []
            for qm in queue_matches:
                queue_nums.extend(re.findall(r'(\d\.\d)', qm))
            
            if not queue_nums:
                continue
            
            # Pattern 1: Full change "раніше – об 11:00 і триватиме до 16:00"
            match = re.search(
                r'раніше\s*-?\s*о[б]?\s*(\d{1,2}:\d{2}).+?триватиме\s+до\s*(\d{1,2}:\d{2})',
                entry, re.IGNORECASE
            )
            if match:
                start, end = self._normalize_time(match.group(1)), self._normalize_time(match.group(2))
                for q in queue_nums:
                    if f"{q}_full" not in processed:
                        queues.setdefault(q, []).append({"start": start, "end": end, "type": "change"})
                        processed.add(f"{q}_full")
                continue
            
            # Pattern 2: Earlier start "розпочнеться раніше – о 20:00"
            match = re.search(r'розпочнеться\s+раніше\s*-?\s*о[б]?\s*(\d{1,2}:\d{2})', entry, re.IGNORECASE)
            if match:
                new_start = self._normalize_time(match.group(1))
                for q in queue_nums:
                    if f"{q}_start" not in processed and f"{q}_full" not in processed:
                        queues.setdefault(q, []).append({"start": new_start, "end": None, "type": "change_start"})
                        processed.add(f"{q}_start")
                continue
            
            # Pattern 3: Extended end "триватиме довше – до 11:00"
            match = re.search(r'триватиме\s+довше\s*-?\s*(?:до|заживлення.+?о[б]?)\s*(\d{1,2}:\d{2})', entry, re.IGNORECASE)
            if match:
                new_end = self._normalize_time(match.group(1))
                for q in queue_nums:
                    if f"{q}_end" not in processed:
                        queues.setdefault(q, []).append({"start": None, "end": new_end, "type": "change_end"})
                        processed.add(f"{q}_end")
                continue
            
            # Pattern 4: Extra outage "додатково буде знеструмлено з 16:00 до 18:00"
            match = re.search(r'додатково.+?з\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})', entry, re.IGNORECASE)
            if match:
                start, end = self._normalize_time(match.group(1)), self._normalize_time(match.group(2))
                for q in queue_nums:
                    queues.setdefault(q, []).append({"start": start, "end": end, "type": "extra"})
    
    def _merge_intervals(self, queues: dict) -> dict:
        """
        Merge intervals and apply changes to build final schedule.
        
        Applies change_start/change_end to nearest base intervals,
        merges overlapping intervals, returns clean result.
        """
        result = {}
        
        for queue, intervals in queues.items():
            base = [i for i in intervals if i["type"] == "base" and i["start"] and i["end"]]
            changes = [i for i in intervals if i["type"] in ("change_start", "change_end")]
            full_changes = [i for i in intervals if i["type"] == "change" and i["start"] and i["end"]]
            extras = [i for i in intervals if i["type"] == "extra" and i["start"] and i["end"]]
            
            base.sort(key=lambda x: x["start"])
            
            # Apply start/end changes to nearest intervals
            for change in changes:
                if not base:
                    continue
                if change["type"] == "change_start" and change["start"]:
                    idx = self._find_nearest(base, change["start"], "start")
                    if idx is not None:
                        base[idx]["start"] = change["start"]
                elif change["type"] == "change_end" and change["end"]:
                    idx = self._find_nearest(base, change["end"], "end")
                    if idx is not None:
                        base[idx]["end"] = change["end"]
            
            # Merge full changes with overlapping base intervals
            for fc in full_changes:
                merged = False
                for bi in base:
                    if self._overlaps(bi, fc):
                        bi["start"] = min(bi["start"], fc["start"])
                        bi["end"] = max(bi["end"], fc["end"])
                        merged = True
                        break
                if not merged:
                    base.append({"start": fc["start"], "end": fc["end"], "type": "base"})
            
            # Add extras
            base.extend({"start": e["start"], "end": e["end"], "type": "base"} for e in extras)
            
            # Merge overlapping and sort
            merged = self._merge_overlapping(base)
            if merged:
                result[queue] = [{"start": i["start"], "end": i["end"], "type": "base"} for i in merged]
        
        return result
    
    def _find_nearest(self, intervals: list, time: str, field: str) -> Optional[int]:
        """Find index of interval with nearest time value."""
        if not intervals:
            return None
        
        time_mins = self._to_minutes(time)
        best_idx, best_diff = 0, float("inf")
        
        for i, interval in enumerate(intervals):
            diff = abs(self._to_minutes(interval[field]) - time_mins)
            if diff < best_diff:
                best_idx, best_diff = i, diff
        
        return best_idx
    
    def _to_minutes(self, time_str: str) -> int:
        """Convert HH:MM to minutes."""
        h, m = time_str.split(":")
        return int(h) * 60 + int(m)
    
    def _overlaps(self, i1: dict, i2: dict) -> bool:
        """Check if two intervals overlap."""
        s1, e1 = self._to_minutes(i1["start"]), self._to_minutes(i1["end"])
        s2, e2 = self._to_minutes(i2["start"]), self._to_minutes(i2["end"])
        return not (e1 <= s2 or e2 <= s1)
    
    def _merge_overlapping(self, intervals: list) -> list:
        """Merge overlapping intervals."""
        if not intervals:
            return []
        
        sorted_ints = sorted(intervals, key=lambda x: self._to_minutes(x["start"]))
        merged = [sorted_ints[0].copy()]
        
        for current in sorted_ints[1:]:
            last = merged[-1]
            if self._to_minutes(current["start"]) <= self._to_minutes(last["end"]):
                if self._to_minutes(current["end"]) > self._to_minutes(last["end"]):
                    last["end"] = current["end"]
            else:
                merged.append(current.copy())
        
        return merged
