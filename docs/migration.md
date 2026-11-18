# 단일 스크립트에서 0.1.0으로 이전

기존 `trending_keywords.py`는 `src/trending_keywords/` 패키지로 분리했습니다. 먼저 `python -m pip install .` 또는 개발용 `python -m pip install -e ".[dev]"`를 실행하세요.

| 기존 | 현재 |
| --- | --- |
| `python trending_keywords.py` | `python -m trending_keywords analyze --db <경로>` |
| 소스의 `DB_DIR` 수정 | CLI의 `--db` |
| 시스템 현재 시각 고정 | `--at` 또는 API의 `now` |
| 모듈 전역 상수 수정 | 불변 `TrendConfig` 또는 CLI 옵션 |
| 실행 시 원본 DB에 자동 저장 | 기본은 읽기만 수행, `--save-db`로 별도 결과 DB 지정 |
| `trending_keywords` 테이블 | `trend_runs`와 `trend_results` |
| SQL 부분 문자열 검색으로 게시물 연결 | 실제 분석에서 등장한 `{community, idx}` 기록 |

`posts` 테이블에 `idx`, `community`, `title`, `views`, `reg_date`가 있으면 입력으로 사용할 수 있습니다. 기존의 `link`, `category` 등 추가 열은 무시합니다. 기존 순위 테이블의 `post_idx_list` 누락 문제는 새 저장 경로와 무관하며, 해당 테이블을 수정할 필요가 없습니다. 과거 결과를 새 스키마로 자동 이전하지는 않습니다.

## API

분석 함수 이름 `trending_keywords()`는 유지합니다. 최근·배경 목록과 `now`를 전달할 수 있고 `config=TrendConfig(...)`를 추가로 받습니다. 최신 API는 결과에 `rank`를 포함하고 `top_n`을 적용합니다.

| 이전 필드 | 현재 필드 |
| --- | --- |
| `key` (tuple) | `tokens` (list) |
| `y` | `weighted_posts` |
| `background` | `background_posts` |
| `ids` (set) | `post_indices` (list) |
| `communities` (Counter) | `communities` (dict) |

직접 DB에 접근하던 저장 함수는 제거했습니다. `storage.save_report()`에 `analyze_posts()`의 보고서를 전달해 저장할 수 있습니다. API에서는 저장 경로를 호출자가 관리합니다.

## 계산 변경

이번 버전은 이전 스크립트의 결과와 완전히 같지 않습니다.

- `half_life_hours`가 실제 반감기를 뜻하도록 `exp(-age / 8)`을 `2 ** (-age / 8)`로 변경했습니다.
- 조회수 중앙값은 짝수 개 표본에서 가운데 두 값의 평균을 사용합니다.
- 3-gram NPMI에 `n - 1` 정규화를 적용했습니다.
- 단일 커뮤니티를 허용했을 때 균형도 배율이 불필요하게 낮아지지 않도록 했습니다.
- `analyze_posts()`는 미래 게시물을 제외합니다.
- 잘못된 날짜는 오류를 반환하고, NaN·무한대·음수 조회수는 0으로 정리합니다.
- 입력 딕셔너리에 `_views`를 추가하지 않습니다.

형태소 분석과 원래의 증가량·커뮤니티 기반 순위 방식은 유지하되, 위 변경으로 점수와 순위가 달라질 수 있습니다. 운영에 적용할 때는 같은 입력·기준 시각으로 결과를 비교하세요.
