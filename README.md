# Trending Keywords

**한국어 게시물 제목에서 지금 새롭게 주목받는 키워드를 찾습니다.**

[Kiwi](https://github.com/bab2min/kiwipiepy) 형태소 분석과 과거 대비 등장량 비교를 결합한 Python 도구입니다. 조회수, 최신성, 여러 커뮤니티로의 확산을 반영해 최근의 인기 키워드를 추출합니다. 소셜 리스닝, 커뮤니티 모니터링, 이슈 탐색에 사용할 수 있습니다.

- **한국어 분석** — 명사·고유 명사·외국어·한자 토큰으로 1~3-gram 후보 생성
- **급상승 탐지** — 최근 16시간을 직전 14일과 비교
- **조회수·최신성 보정** — 커뮤니티별 조회수 중앙값과 8시간 반감기 사용
- **구체적인 키워드 선택** — 구 결합도와 커뮤니티 조건으로 필터링하고 포함 관계 정리
- **바로 실행하는 데모** — 실제 DB에서 가명화·축약한 768건의 샘플 포함
- **Python API · CLI** — JSONL / SQLite 입력, JSON 출력, 선택적인 실행 이력 저장

수집기나 웹 서비스는 포함하지 않습니다. 분석 대상은 게시물 **제목**이며, API 키나 외부 추론 서비스 없이 로컬에서 실행합니다.

## 빠른 시작

Python **3.10 이상**이 필요합니다. 저장소를 내려받고 프로젝트 루트에서 실행하세요. 아직 PyPI에 배포한 패키지가 아니므로 아래처럼 로컬 소스를 설치합니다.

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m trending_keywords demo
```

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m trending_keywords demo
```

아래 문서의 `python`은 패키지를 설치한 가상환경의 Python을 뜻합니다. 가상환경을 활성화하거나 위의 실행 파일 경로로 바꾸세요. 활성화한 환경에서는 `trending-keywords` 명령도 사용할 수 있습니다.

기본 데모의 실행 결과입니다. Windows / Python 3.13.16 / kiwipiepy 0.24.1에서 확인했습니다.

```text
at=2026-11-09 23:52:00  recent=131  background=637
rank  score     lift    posts  keyword
   1      7.10     5.4     12  한국 시리즈 우승
   2      5.93     7.7     13  결승
   3      5.32     4.1     12  구자욱
```

`demo`는 샘플의 기준 시각을 사용하므로 실행 날짜가 달라져도 같은 기간을 분석합니다. 결과는 샘플의 단어 분포를 보여주며 실제 사건에 대한 사실 확인 결과가 아닙니다. 형태소 분석기 버전을 바꾸면 결과가 달라질 수 있습니다.

## 내 데이터 분석하기

### JSONL

한 줄에 게시물 하나를 담은 UTF-8 JSON 파일을 준비합니다.

```json
{"idx":"p1","community":"community_a","title":"우주 망원경 관측 성공","views":1200,"reg_date":"2026-11-09 18:30:00"}
```

```bash
python -m trending_keywords analyze --input local/posts.jsonl --at "2026-11-09 23:52:00"
```

위 한 줄은 입력 형식 예시입니다. 키워드 추출에는 최근·배경 구간의 충분한 게시물이 필요합니다. 포함된 샘플을 직접 분석할 수도 있습니다.

```bash
python -m trending_keywords analyze --input src/trending_keywords/data/sample_posts.jsonl --at "2026-11-09 23:52:00"
```

| 필드 | 설명 |
| --- | --- |
| `idx` | 게시물 ID. JSONL/API에서 생략하면 입력 순번을 사용합니다. |
| `community` | 비어 있지 않은 출처 식별자. ID는 커뮤니티 안에서 고유해야 합니다. |
| `title` | 비어 있지 않은 제목 문자열 |
| `views` | 조회수. 누락·음수·변환 불가·NaN·무한대는 0으로 처리합니다. |
| `reg_date` | 기준 시각과 같은 시간대의 `YYYY-MM-DD HH:MM:SS` 문자열 |

조회수 0인 게시물은 가중 등장량에 기여하지 않습니다. 날짜는 소수점 이하 초도 허용합니다. 시간대 오프셋이 있는 값은 받지 않으므로 UTC나 한국 시각 등 **한 기준으로 통일한 뒤 시간대 없는 값**을 전달하세요. 작성 시각과 수집 시각 중 무엇을 사용하는지도 데이터 전체에서 일관되어야 합니다.

### SQLite

기존 DB에 `posts` 테이블과 `idx`, `community`, `title`, `views`, `reg_date` 열이 있으면 바로 읽을 수 있습니다. 다른 열이 더 있어도 됩니다.

```bash
python -m trending_keywords analyze --db local/posts.sqlite3 --at "2026-11-09 23:52:00"
```

SQLite의 날짜는 인덱스를 사용하는 범위 조회를 위해 `YYYY-MM-DD HH:MM:SS[.ffffff]` 형식의 TEXT로 통일하세요. `reg_date` 인덱스를 권장합니다. 기본 실행은 입력 DB를 **읽기 전용**으로 열며 테이블을 변경하지 않습니다.

새 DB를 준비하려면 다음 명령으로 최소 스키마를 생성한 뒤 자신의 수집 파이프라인에서 데이터를 넣으세요.

```bash
python -m trending_keywords init-db local/posts.sqlite3
```

포함된 샘플로 SQLite 입력부터 결과 저장까지 확인하려면 다음 예제를 실행합니다. 기존 샘플 DB가 있으면 새 디렉터리를 지정하세요.

```bash
python examples/sqlite_demo.py --directory local/first-demo
```

### 결과 출력과 저장

```bash
# JSON을 표준 출력으로 반환
python -m trending_keywords demo --format json

# 파일로 저장
python -m trending_keywords demo --format json --output outputs/demo.json

# 별도 SQLite에 실행 이력 저장
python -m trending_keywords demo --save-db local/results.sqlite3
```

`--at`을 생략한 `analyze`는 실행 시스템의 현재 로컬 시각을 기준으로 합니다. 과거 DB를 재현할 때는 반드시 `--at`을 지정하세요.

결과 DB에는 설정·분석 기간·상세 결과가 담긴 `trend_runs`와 순위별 `trend_results`가 생성됩니다. 매 실행에 고유한 ID를 부여하고 한 트랜잭션으로 저장하며, 결과가 없는 실행도 기록합니다. 입력 DB와 같은 경로에는 저장할 수 없습니다. [스키마와 이력 조회](docs/usage.md)를 참고하세요.

## Python API

```python
from trending_keywords import TrendConfig, analyze_posts
from trending_keywords.sample import load_sample

posts, metadata = load_sample()
report = analyze_posts(
    posts,
    now=metadata["analysis_at"],
    config=TrendConfig(top_n=10, min_lift=3.5),
)

for row in report["keywords"]:
    print(row["rank"], row["keyword"], row["score"], row["post_refs"])
```

`analyze_posts()`가 날짜로 최근·배경 구간을 나누고 미래 게시물을 제외합니다. 이미 두 구간으로 분리했다면 `trending_keywords(recent_posts, background_posts, now=..., config=...)`를 사용할 수 있습니다. 이 함수의 배경 입력에는 `title`만 있으면 됩니다. 두 함수 모두 원본 입력을 수정하지 않고 JSON으로 직렬화 가능한 결과를 반환합니다.

| 주요 결과 필드 | 의미 |
| --- | --- |
| `rank`, `keyword`, `tokens` | 순위, 표시 문자열, 구성 토큰 |
| `score` | 최종 순위 점수 |
| `z`, `lift`, `excess` | 배경 대비 증가 지표, 등장 배율, 기대량 초과분 |
| `posts`, `weighted_posts`, `background_posts` | 최근 등장 게시물 수, 최근 가중 등장량, 배경 등장 게시물 수 |
| `npmi`, `balance` | 구 결합도와 커뮤니티 분포 균형도 |
| `communities` | 커뮤니티별 최근 등장 게시물 수 |
| `post_refs` | 실제 해당 후보가 등장한 게시물의 `{community, idx}` 목록 |
| `post_indices` | 최근 게시물 목록 안에서의 0부터 시작하는 순번 |

키워드는 원문의 부분 문자열이 아니라 추출한 토큰 조합입니다. 예를 들어 `한국시리즈`가 `한국 시리즈`로 표시될 수 있습니다.

## 동작 원리

```mermaid
flowchart LR
    A[게시물 제목] --> B[최근 · 배경 구간 분리]
    B --> C[Kiwi 형태소 분석]
    C --> D[1~3-gram 문서 빈도]
    D --> E[조회수 · 최신성 가중치]
    E --> F[배경 대비 증가량 평가]
    F --> G[구 결합도 · 커뮤니티 조건]
    G --> H[점수 정렬 · 중복 후보 정리]
```

1. 최근 제목에서 자주 관측되는 세 글자 고유 명사를 Kiwi 사용자 사전에 추가합니다.
2. 토큰별 불용어를 제외하고 1~3-gram을 생성합니다. 같은 후보가 한 제목에 반복되어도 한 번만 셉니다.
3. 커뮤니티별 조회수 중앙값에 대한 로그 비율과 시간 감쇠를 곱해 최근 게시물에 가중치를 부여합니다.
4. 배경 구간의 문서 빈도로 기대량을 계산하고 최근 가중 등장량과 비교합니다.
5. 최소 등장 수, 증가 배율, 구 결합도, 커뮤니티 조건을 만족한 후보를 점수순으로 정렬합니다.
6. 긴 키워드가 짧은 키워드의 등장을 충분히 설명하면 짧은 후보를 제거합니다.

```text
recency = 2 ^ (-age_hours / half_life_hours)
score   = excess × log(lift) × (0.4 + 0.6 × balance)
```

`z`는 가중 등장량을 이용한 탐지 지표이며 통계 검정의 유의확률을 뜻하지 않습니다. 수식과 처리 세부 사항은 [알고리즘 문서](docs/algorithm.md)에 정리했습니다.

## 설정

```bash
python -m trending_keywords analyze --db local/posts.sqlite3 --window-hours 24 --half-life-hours 12 --min-lift 4 --top 20
python -m trending_keywords analyze --help
```

| 설정 / CLI | 기본값 | 설명 |
| --- | --- | --- |
| `window_hours` / `--window-hours` | 16 | 최근 구간 길이(시간) |
| `background_days` / `--background-days` | 14 | 최근 구간 직전의 배경 기간(일) |
| `half_life_hours` / `--half-life-hours` | 8 | 가중치가 절반이 되는 시간 |
| `min_posts` / `--min-posts` | 4 | 최소 최근 등장 게시물 수 |
| `min_communities` / `--min-communities` | 2 | 최소 커뮤니티 수 |
| `min_posts_per_community` / `--min-posts-per-community` | 2 | 커뮤니티별 최소 등장 게시물 수 |
| `min_z` / `--min-z` | 3.0 | 최소 증가 지표 |
| `min_lift` / `--min-lift` | 3.5 | 최소 배경 대비 등장 배율 |
| `min_npmi` / `--min-npmi` | 0.25 | 2~3-gram 최소 결합도 |
| `top_n` / `--top` | 40 | 최대 결과 수 |

추가 불용어는 `--stopwords local/stopwords.txt`로 지정합니다. 한 줄에 한 단어를 쓰며 빈 줄과 `#`으로 시작하는 주석은 무시합니다. 기본 불용어는 유지됩니다. 더 세부적인 설정은 [TrendConfig](src/trending_keywords/config.py)로 조정할 수 있습니다.

## 샘플 데이터

샘플은 제공된 SQLite DB의 대상 기간 18,650건 중 스포츠·게임 용어 조건을 만족한 **768건**에서 만들었습니다. 임의로 생성한 게시물은 아닙니다.

- 원문 제목에서 공개된 허용 목록의 용어만 원래 순서대로 추출했습니다.
- 조회수와 시각은 유지하고, 원본 ID와 출처 이름은 대체했습니다.
- URL, 본문, 작성자 정보, 원본 DB는 포함하지 않았습니다.
- 고정된 분석 시각, 생성 방법, SHA-256을 함께 제공합니다.

원문을 가공한 데모 데이터이므로 원문 분석 정확도나 일반적인 커뮤니티 트렌드의 평가 자료로 사용하지 마세요. [데이터 설명](src/trending_keywords/data/README.md)과 [재생성 스크립트](scripts/build_sample.py)를 참고하세요.

## 한계

- 입력한 커뮤니티의 관심을 분석하며 전체 한국어 사용자의 인기 순위를 대표하지 않습니다.
- 수집 누락, 수집 주기의 변화, 재게시·중복 게시물은 결과에 영향을 줍니다. 중복 제거는 입력 단계에서 처리하세요.
- 제목만 사용하며 동의어 통합, 의미 기반 주제 묶기, 감성 분석은 하지 않습니다.
- 조회수가 없거나 단일 커뮤니티만 있는 데이터는 기본 설정에 적합하지 않습니다. 단일 커뮤니티 분석에는 `--min-communities 1`을 사용하세요.
- 매 실행마다 대상 구간을 메모리에 읽고 형태소를 분석합니다. 대규모 증분 처리나 처리 성능 보장은 제공하지 않습니다.
- 자동 실행은 운영체제 스케줄러 등 외부 도구에서 구성해야 합니다.

## 개발

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
```

GitHub Actions에는 Windows·macOS·Linux와 Python 3.10·3.13의 테스트 및 wheel 설치 검증을 구성했습니다. 로컬 검증은 Windows / Python 3.13에서 수행했습니다. 다른 환경의 CI 결과는 저장소를 GitHub에 올린 뒤 확인할 수 있습니다.

```text
.
├── src/trending_keywords/    # 설치되는 패키지
│   ├── core.py              # 분석·순위 계산
│   ├── tokenization.py      # 형태소 분석·후보 생성
│   ├── config.py            # 설정과 검증
│   ├── storage.py           # JSONL·SQLite 입출력
│   ├── cli.py               # 명령행 인터페이스
│   └── data/                # DB 기반 샘플·메타데이터·허용 용어
├── examples/                # SQLite 실행 예제
├── scripts/                 # 샘플 재생성
├── tests/                   # 회귀·입출력·CLI 테스트
├── docs/                    # 알고리즘·스키마·마이그레이션
├── .github/                 # CI·Issue·PR 템플릿
└── pyproject.toml           # 패키지·의존성·도구 설정
```
