#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# check_log.py
# 2023-11-20 by NineD77
# 2024-06-10 by NineD77 - 여러 개선
#   - Fail 처리 후 다음 OK 처리 시 wrap-around 체크 및 사이클 종료
#   - 사이클 시간 계산 시 타임스탬프가 있는 줄의 타임스탬프만 반영
#   - 체크리스트 파일의 서브 항목이 부모 없는 경우 경고 출력   
#   - 체크리스트 파일의 라인 형식 오류(컬럼 수 부족) 경고 출력
#   - 결과 파일에 모든 사이클 요약 추가
#   - 체크리스트 파일의 패턴이 없는 경우 경고 출력

import sys
import re
import os
from datetime import datetime as dt

class ChecklistItem:
    """체크리스트 항목"""
    def __init__(self, label, ok_text, fail_text, patterns, not_patterns, is_sub=False):
        self.label = label
        self.ok_text = ok_text
        self.fail_text = fail_text
        self.patterns = [re.compile(p) for p in patterns]
        self.not_patterns = [re.compile(p) for p in not_patterns]
        self.is_sub = is_sub
        self.parent = None

class CycleResult:
    def __init__(self, number, ok_count, fail_count):
        self.number = number
        self.ok_count = ok_count
        self.fail_count = fail_count

def parse_timestamp(log_timestamp: str) -> dt:
    ts = log_timestamp.strip("[]").split("][")[0]
    date_part, time_part = ts.split("-")
    time_main, ms = time_part.split(":")
    dt_str = f"{date_part} {time_main}.{ms}"
    return dt.strptime(dt_str, "%Y.%m.%d %H.%M.%S.%f")

class LogChecker:
    def __init__(self, log_file, check_file, output_file=None):
        self.log_file = log_file
        self.check_file = check_file
        self.output_file = output_file   # ✅ 추가
        self.checklist = self.load_checklist()
        self.results = []
        self.cycle_summary = []

        self.current_index = 0
        self.ok_count = 0
        self.fail_count = 0
        self.cycle_count = 0
        self.cycle_start_time = None
        self.cycle_end_time = None

        self.matched_items_in_cycle = set()
        self.ts_pattern = re.compile(r"(\[\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3}\])")

    # 서브가 활성화되어 검사 대상인지 (부모가 OK 되었는지) 확인
    def is_parent_matched(self, item) -> bool:
        if not item.is_sub:
            return True
        return (item.parent in self.matched_items_in_cycle)

    def match_pattern(self, patterns, line):
        for p in patterns:
            if p.search(line):
                return p.pattern
        return None

    # 변경: 이제 이 함수는 "OK로 확정"될 때만 호출합니다.
    def update_cycle_time(self, log_time):
        if log_time:
            if not self.cycle_start_time:
                self.cycle_start_time = log_time
            self.cycle_end_time = log_time

    def add_result(self, msg):
        self.results.append(msg)

    def mark_fail(self, item, extra=""):
        if item.fail_text:
            self.add_result(f"{item.label}: {item.fail_text} {extra}")
        self.fail_count += 1

    def load_checklist(self):
        items = []
        last_main = None
        with open(self.check_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '|' not in line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) != 6:
                    print(f"[경고] 체크리스트 라인 형식 오류(6컬럼 아님): {line}")
                    continue
                sub_flag, label, ok_text, fail_text, not_pattern_str, pattern_str = parts
                patterns = [p for p in pattern_str.split(';') if p.strip()]
                not_patterns = [p for p in not_pattern_str.split(';') if p.strip()]
                is_sub = (sub_flag.lower() in ("1", "y", "yes", "true"))
                item = ChecklistItem(label, ok_text, fail_text, patterns, not_patterns, is_sub)
                if is_sub and last_main:
                    item.parent = last_main
                else:
                    last_main = item
                items.append(item)
        return items

    def check_fail_overlap(self, line):
        """현재 인덱스 다음부터 끝 + 0번 검사 (서브는 부모 OK된 경우만 후보).
           not_patterns까지 고려해서 진짜 OK 후보만 반환.
        """
        if self.current_index == 0:
            return None

        total_len = len(self.checklist)
        fail_indices = list(range(self.current_index + 1, total_len)) + [0]

        for next_index in fail_indices:
            next_item = self.checklist[next_index]
            if not self.is_parent_matched(next_item):
                continue
            pat = self.match_pattern(next_item.patterns, line)
            if not pat:
                continue
            if self.match_pattern(next_item.not_patterns, line):
                continue
            return next_index
        return None

    def handle_fail_next(self, line_num, next_index, line, log_time):
        """
        Fail 처리 후 next_index 항목을 OK로 처리.
        wrap-around 시(다시 0으로 돌아갈 때) 이전 사이클을 먼저 complete_cycle()로 끊는다.
        """
        total_len = len(self.checklist)
        if self.current_index < next_index:
            indices = range(self.current_index, next_index)
        else:
            indices = list(range(self.current_index, total_len)) + list(range(0, next_index))

        for i in indices:
            item = self.checklist[i]
            # 부모 없는 서브는 skip (Fail도 없음)
            if item.is_sub and not self.is_parent_matched(item):
                continue
            self.mark_fail(item, f"(patterns={item.patterns})")

        wrapped = next_index < self.current_index
        if wrapped:
            # 이전 사이클을 명확히 끊는다 (이때 사이클 종료 시간은 마지막으로 OK 처리된 항목의 타임스탬프)
            self.complete_cycle(tag="wrap-around before next OK")

        next_item = self.checklist[next_index]
        if not self.is_parent_matched(next_item):
            self.set_current_Index((next_index + 1) % total_len, tag="parent not matched for next OK")
            return

        # 이제 이 줄은 새 사이클(또는 현재 사이클)의 OK가 된다 — 타임스탬프 반영
        self.update_cycle_time(log_time)

        if self.match_pattern(next_item.not_patterns, line):
            self.mark_fail(next_item, f"(unexpected match, not_patterns={next_item.not_patterns})")
        else:
            self.add_result(f"{next_item.label}: {next_item.ok_text}")
            self.add_result(f"  >> (Line {line_num}) {line}")
            self.ok_count += 1
            self.matched_items_in_cycle.add(next_item)

        self.set_current_Index((next_index + 1) % total_len, tag="after handling fail-next")

    def complete_cycle(self, tag=""):
        self.cycle_count += 1
        tag_info = f" [{tag}]" if tag else ""
        total_time = None
        if self.cycle_start_time and self.cycle_end_time:
            total_time = (self.cycle_end_time - self.cycle_start_time).total_seconds()
        time_info = f" | Total Time : {int(total_time // 60)}:{int(total_time % 60)} (Sec)" if total_time else "0 (Sec)"
        self.add_result(
            f"\n=== No# {self.cycle_count} Checklist cycle complete "
            f"(Ok: {self.ok_count}, Fail: {self.fail_count}){time_info}{tag_info} ===\n"
        )
        self.cycle_summary.append(CycleResult(self.cycle_count, self.ok_count, self.fail_count))
        # reset for next cycle
        self.ok_count = 0
        self.fail_count = 0
        self.current_index = 0
        self.cycle_start_time = None
        self.cycle_end_time = None
        self.matched_items_in_cycle = set()

    def set_current_Index(self, NewIndex, tag="Unknown"):
        if self.current_index >= NewIndex:
            self.complete_cycle(tag)
            return
        self.current_index = NewIndex

    def process_log(self):
        total_len = len(self.checklist)
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.rstrip("\n")
                m = self.ts_pattern.match(line)
                log_time = parse_timestamp(m.group(1)) if m else None

                # 중요: 여기선 update_cycle_time 호출하지 않음 (OK로 확정될 때만 호출)

                # 선행 항목 오버랩 검사
                fail_index = self.check_fail_overlap(line)
                if fail_index is not None:
                    self.handle_fail_next(line_num, fail_index, line, log_time)
                    continue

                current_item = self.checklist[self.current_index]

                # 서브인데 부모가 아직 OK가 아니라면 대기(스킵)
                if not self.is_parent_matched(current_item):
                    continue

                matched_pattern = self.match_pattern(current_item.patterns, line)

                if matched_pattern and not self.match_pattern(current_item.not_patterns, line):
                    # OK 확정 → 이 줄의 타임스탬프로 사이클 시간 갱신
                    self.update_cycle_time(log_time)
                    self.add_result(f"{current_item.label}: {current_item.ok_text}, match=[{matched_pattern}]")
                    self.add_result(f"  >> (Line {line_num}) {line}")
                    self.ok_count += 1
                    self.matched_items_in_cycle.add(current_item)
                    self.set_current_Index((self.current_index + 1) % total_len, "normal completion")
                elif matched_pattern:
                    self.mark_fail(current_item, f"(unexpected match, not_patterns={current_item.not_patterns})")

        # 로그 끝에서 미완료 사이클이 있으면 잔여 Fail 처리 후 사이클 종료
        if self.current_index > 0:
            for i in range(self.current_index, total_len):
                item = self.checklist[i]
                if not self.is_parent_matched(item):
                    continue
                self.mark_fail(item, f"(not found in last cycle, patterns={item.patterns})")
            self.complete_cycle(tag="end of log")

    def save_results(self):
        if self.output_file:  # ✅ 인자로 받은 파일명 우선
            result_file = self.output_file
        else:
            base_name = os.path.splitext(os.path.basename(self.log_file))[0]
            result_dir = "ND_Results"
            result_file = os.path.join(result_dir, f"report_{base_name}.txt")

        # ✅ 디렉토리 생성 (output_file 포함 경우도 지원)
        os.makedirs(os.path.dirname(result_file), exist_ok=True)

        summary_lines = ["=== All Cycles Summary ==="] + [
            f"No# {c.number}: Ok={c.ok_count}, Fail={c.fail_count}" for c in self.cycle_summary
        ]
        output = "\n".join(self.results + summary_lines)
        print(output)
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"\n[INFO] 결과가 '{result_file}' 파일로 저장되었습니다.")

def main():
    if len(sys.argv) < 3:
        print("Usage: python check_log.py <log_file> <check_file> [output_file]")
        sys.exit(1)

    log_file, check_file = sys.argv[1], sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    checker = LogChecker(log_file, check_file, output_file)
    checker.process_log()
    checker.save_results()

if __name__ == "__main__":
    main()
