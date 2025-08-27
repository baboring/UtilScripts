import os
import sys

def load_keywords(keyword_arg_or_file):
    """키워드 인자(문자열 or 파일경로)를 받아서 리스트 반환"""
    if os.path.exists(keyword_arg_or_file):  # 파일이면 줄 단위 키워드 로드
        with open(keyword_arg_or_file, "r", encoding="utf-8") as f:
            keywords = [line.strip() for line in f if line.strip()]
        print(f"[INFO] 키워드 {len(keywords)}개 로드됨 (파일: {keyword_arg_or_file})")
        return keywords
    else:
        # 쉼표(,)로 구분된 키워드 직접 입력도 허용
        return [k.strip() for k in keyword_arg_or_file.split(",") if k.strip()]

def split_log_file(input_file, keywords, output_dir="splitted_logs"):
    if not os.path.exists(input_file):
        print(f"[Error] 입력한 파일이 존재하지 않습니다: {input_file}")
        return

    if not keywords:
        print("[Error] 키워드가 비어있습니다.")
        return

    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_file))[0]  # 파일명(확장자 제거)

    with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    part = 0
    buffer = []
    last_was_keyword = False  # 직전 줄이 키워드였는지 확인

    for line in lines:
        if any(keyword in line for keyword in keywords):  # 키워드 발견
            if buffer and not last_was_keyword:
                # 이전 버퍼 저장 (키워드 연속일 때는 저장 안함 → 묶기)
                part_filename = os.path.join(output_dir, f"{base_name}_part_{part:03d}.log")
                with open(part_filename, "w", encoding="utf-8") as out:
                    out.writelines(buffer)
                print(f"[생성됨] {part_filename} ({len(buffer)} lines)")
                buffer = []
                part += 1
            last_was_keyword = True
        else:
            last_was_keyword = False

        buffer.append(line)  # 기준 줄도 포함

    # 마지막 남은 버퍼 저장
    if buffer:
        part_filename = os.path.join(output_dir, f"{base_name}_part_{part:03d}.log")
        with open(part_filename, "w", encoding="utf-8") as out:
            out.writelines(buffer)
        print(f"[생성됨] {part_filename} ({len(buffer)} lines)")

    print(f"\n[완료] {base_name}: 총 {part+1} 개의 파일이 생성되었습니다. 출력폴더: {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python split_log.py <로그파일경로> <키워드 or 키워드파일> [출력폴더]")
        print("예시1: python split_log.py server.log ERROR")
        print("예시2: python split_log.py server.log ERROR,WARN,CRITICAL")
        print("예시3: python split_log.py server.log keywords.txt")
        sys.exit(1)

    input_file = sys.argv[1]
    keyword_arg_or_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "splitted_logs"

    keywords = load_keywords(keyword_arg_or_file)
    split_log_file(input_file, keywords, output_dir)
