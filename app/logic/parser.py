import re
from datetime import datetime

class OutageParser:
    def __init__(self):
        # Патерни
        self.date_text_p = r"на (\d{2}\.\d{2}\.\d{4})"
        self.date_alt_p = r"ГПВ-(\d{2}\.\d{2}\.\d{2})"
        self.base_p = r"підчерга (\d\.\d) [–—-] з (.+?)(?:;|\.|$)"
        self.time_p = r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})"

    def extract_dates(self, text, alts):
        """Шукає всі дати на сторінці"""
        dates = set()
        # З тексту заголовків
        for d in re.findall(self.date_text_p, text):
            dates.add(datetime.strptime(d, "%d.%m.%Y").strftime("%Y-%m-%d"))
        
        # З alt-текстів картинок (напр. ГПВ-15.01.26)
        for alt in alts:
            match = re.search(self.date_alt_p, alt)
            if match:
                d_obj = datetime.strptime(match.group(1), "%d.%m.%y")
                dates.add(d_obj.strftime("%Y-%m-%d"))
        return list(dates)

    def parse_content(self, text):
        results = {}
        # Базовий графік
        for q, hours in re.findall(self.base_p, text):
            times = re.findall(self.time_p, hours)
            results[q] = [{"start": t[0], "end": t[1], "type": "base"} for t in times]
        
        # Оперативні зміни
        extra_p = r"підчергу (\d\.\d)\.? додатково.+?з (\d{2}:\d{2}) до (\d{2}:\d{2})"
        for q, s, e in re.findall(extra_p, text):
            if q in results: results[q].append({"start": s, "end": e, "type": "extra"})
        
        return results