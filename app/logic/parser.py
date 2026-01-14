import re
from datetime import datetime

class OutageParser:
    def __init__(self):
        # Патерни для дати та підчерг
        self.date_p = r"відключень на (\d{2}\.\d{2}\.\d{4})"
        self.base_p = r"підчерга (\d\.\d) [–—-] з (.+?)(?:;|\.|$)"
        self.time_p = r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})"

    def extract_date(self, text):
        match = re.search(self.date_p, text)
        if match:
            return datetime.strptime(match.group(1), "%d.%m.%Y").strftime("%Y-%m-%d")
        return None

    def parse_content(self, text):
        results = {}
        # Базовий графік
        for q, hours in re.findall(self.base_p, text):
            times = re.findall(self.time_p, hours)
            results[q] = [{"start": t[0], "end": t[1], "type": "base"} for t in times]
        
        # Оперативні зміни: додатково, раніше, довше
        extra_p = r"підчергу (\d\.\d)\.? додатково.+?з (\d{2}:\d{2}) до (\d{2}:\d{2})"
        earlier_p = r"підчерги (\d\.\d)\.? відключення розпочнеться раніше – о[б]? (\d{2}:\d{2})"
        longer_p = r"підчерги (\d\.\d)\.? відключення триватиме довше – до (\d{2}:\d{2})"

        for q, s, e in re.findall(extra_p, text):
            if q in results: results[q].append({"start": s, "end": e, "type": "extra"})
        
        for q, ns in re.findall(earlier_p, text):
            if q in results:
                results[q][0]["start"] = ns
                results[q][0]["type"] = "change"

        for q, ne in re.findall(longer_p, text):
            if q in results:
                results[q][-1]["end"] = ne
                results[q][-1]["type"] = "change"

        return results
