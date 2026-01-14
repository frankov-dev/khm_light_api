import re
from datetime import datetime

class OutageParser:
    def __init__(self):
        # Патерни для парсингу часових інтервалів
        self.queue_pattern = re.compile(
            r'підчерга\s+(\d\.\d)\s*[–—-]\s*(.+?)(?=підчерга|\Z)',
            re.IGNORECASE | re.DOTALL
        )
        self.time_pattern = re.compile(r'з\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})')

    def parse_schedule_block(self, block):
        """
        Парсить один блок графіка для конкретної дати.
        block: {"date": "2026-01-15", "schedule_text": "...", "extras_text": "..."}
        Повертає: {"date": "2026-01-15", "queues": {"1.1": [...], "1.2": [...], ...}}
        """
        result = {
            "date": block["date"],
            "queues": {}
        }
        
        schedule_text = block.get("schedule_text", "")
        extras_text = block.get("extras_text", "")
        
        # Парсимо основний графік
        # Спершу розбиваємо по рядках і шукаємо кожну підчергу
        lines = schedule_text.split('\n')
        
        for line in lines:
            # Шукаємо номер підчерги
            queue_match = re.search(r'підчерга\s+(\d\.\d)', line, re.IGNORECASE)
            if queue_match:
                queue_num = queue_match.group(1)
                
                # Шукаємо всі часові інтервали в цьому рядку
                times = self.time_pattern.findall(line)
                
                intervals = []
                for start, end in times:
                    # Нормалізуємо формат часу (7:00 -> 07:00)
                    start = self._normalize_time(start)
                    end = self._normalize_time(end)
                    intervals.append({
                        "start": start,
                        "end": end,
                        "type": "base"
                    })
                
                if intervals:
                    result["queues"][queue_num] = intervals
        
        # Парсимо оперативні зміни
        self._parse_extras(extras_text, result["queues"])
        
        return result

    def _normalize_time(self, time_str):
        """Нормалізує час до формату HH:MM"""
        parts = time_str.split(':')
        hour = parts[0].zfill(2)
        minute = parts[1].zfill(2) if len(parts) > 1 else "00"
        return f"{hour}:{minute}"

    def _parse_extras(self, extras_text, queues):
        """
        Парсить оперативні зміни та додає їх до відповідних черг.
        Приклади:
        - "підчергу 1.2. додатково буде знеструмлено з 16:00 до 18:00"
        - "у підчерги 4.2. відключення розпочнеться раніше – о 14:00"
        - "у підчерги 6.1. відключення триватиме довше – до 14:00"
        """
        if not extras_text:
            return
        
        # Додаткові відключення
        extra_pattern = re.compile(
            r'підчерг[у|и]\s+(\d\.\d)\.?\s+додатково.+?з\s*(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})',
            re.IGNORECASE
        )
        for match in extra_pattern.finditer(extras_text):
            queue_num = match.group(1)
            start = self._normalize_time(match.group(2))
            end = self._normalize_time(match.group(3))
            
            if queue_num in queues:
                queues[queue_num].append({
                    "start": start,
                    "end": end,
                    "type": "extra"
                })
        
        # Відключення раніше - модифікуємо існуючий інтервал
        earlier_pattern = re.compile(
            r'підчерг[у|и]\s+(\d\.\d)\.?\s+відключення\s+розпочнеться\s+раніше\s*[–—-]?\s*о?\s*(\d{1,2}:\d{2})',
            re.IGNORECASE
        )
        for match in earlier_pattern.finditer(extras_text):
            queue_num = match.group(1)
            new_start = self._normalize_time(match.group(2))
            
            if queue_num in queues:
                queues[queue_num].append({
                    "start": new_start,
                    "end": None,  # Буде з'єднано з наступним інтервалом
                    "type": "change_start"
                })
        
        # Відключення довше - модифікуємо існуючий інтервал
        longer_pattern = re.compile(
            r'підчерг[уи|и]\s+(\d\.\d)\.?\s+відключення\s+триватиме\s+довше\s*[–—-]?\s*до\s*(\d{1,2}:\d{2})',
            re.IGNORECASE
        )
        for match in longer_pattern.finditer(extras_text):
            queue_num = match.group(1)
            new_end = self._normalize_time(match.group(2))
            
            if queue_num in queues:
                queues[queue_num].append({
                    "start": None,
                    "end": new_end,
                    "type": "change_end"
                })

    # Старі методи для зворотної сумісності
    def extract_dates(self, text, alts):
        """Шукає всі дати на сторінці (старий метод)"""
        date_text_p = r"на (\d{2}\.\d{2}\.\d{4})"
        date_alt_p = r"ГПВ-(\d{2}\.\d{2}\.\d{2})"
        
        dates = set()
        for d in re.findall(date_text_p, text):
            dates.add(datetime.strptime(d, "%d.%m.%Y").strftime("%Y-%m-%d"))
        
        for alt in alts:
            match = re.search(date_alt_p, alt)
            if match:
                d_obj = datetime.strptime(match.group(1), "%d.%m.%y")
                dates.add(d_obj.strftime("%Y-%m-%d"))
        return list(dates)

    def parse_content(self, text):
        """Старий метод парсингу (для сумісності)"""
        base_p = r"підчерга (\d\.\d) [–—-] з (.+?)(?:;|\.|$)"
        time_p = r"(\d{2}:\d{2})\s+до\s+(\d{2}:\d{2})"
        
        results = {}
        for q, hours in re.findall(base_p, text):
            times = re.findall(time_p, hours)
            results[q] = [{"start": t[0], "end": t[1], "type": "base"} for t in times]
        
        extra_p = r"підчергу (\d\.\d)\.? додатково.+?з (\d{2}:\d{2}) до (\d{2}:\d{2})"
        for q, s, e in re.findall(extra_p, text):
            if q in results:
                results[q].append({"start": s, "end": e, "type": "extra"})
        
        return results