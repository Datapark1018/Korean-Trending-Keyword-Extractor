# 입력·저장·문제 해결

## 입력 DB

`python -m trending_keywords init-db local/posts.sqlite3`는 다음 스키마를 만듭니다. 기존 행은 유지하며 기존 테이블을 마이그레이션하지 않습니다.

```sql
CREATE TABLE IF NOT EXISTS posts (
    idx TEXT NOT NULL,
    community TEXT NOT NULL,
    title TEXT NOT NULL,
    views INTEGER NOT NULL DEFAULT 0,
    reg_date TEXT NOT NULL,
    PRIMARY KEY (community, idx)
);
CREATE INDEX IF NOT EXISTS idx_posts_reg_date ON posts(reg_date);
```

`idx`만 같고 `community`가 다른 게시물은 구분됩니다. JSONL/API 입력에서 ID를 생략하면 입력 순번으로 대체하지만, 실제 서비스 연동에는 안정적인 ID를 제공하세요. 중복 ID나 중복 게시물은 입력 전에 정리해야 합니다.

입력 DB는 `mode=ro`, `PRAGMA query_only=ON`으로 엽니다. 존재하지 않는 경로를 주어도 빈 DB를 만들지 않습니다. WAL 모드 DB는 SQLite가 일관된 상태로 읽을 수 있는 디렉터리 권한과 관련 파일이 필요합니다. 사용 중인 DB 파일 하나만 복사하면 WAL에 남아 있는 데이터가 빠질 수 있으므로 SQLite 백업 API 등으로 일관된 사본을 준비하세요.

## JSON 출력

보고서는 다음 정보를 담습니다.

- `schema_version`: 보고서 형식 버전(현재 1)
- `analysis_at`, `recent_start`, `background_start`: 기간 경계
- `recent_posts`, `background_posts`: 각 구간에 포함된 게시물 수
- `config`: 사용한 전체 설정과 불용어
- `keywords`: 점수·문서 수·참조 정보를 포함한 결과

`--format json`의 표준 출력에는 JSON만 출력합니다. `--save-db`의 저장 안내는 표준 오류로 보냅니다. 정상 실행은 결과가 비어 있어도 종료 코드 0, 잘못된 입력이나 I/O 오류는 2입니다.

## 결과 DB

`--save-db local/results.sqlite3`를 명시한 경우에만 저장합니다. 기존 단일 파일 버전의 `trending_keywords` 테이블은 수정하지 않습니다.

```sql
CREATE TABLE trend_runs (
    run_id TEXT PRIMARY KEY,
    analysis_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    report_json TEXT NOT NULL
);

CREATE TABLE trend_results (
    run_id TEXT NOT NULL REFERENCES trend_runs(run_id),
    rank INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    score REAL NOT NULL,
    post_refs_json TEXT NOT NULL,
    PRIMARY KEY (run_id, rank)
);
```

`analysis_at`은 분석 대상 시각이고, `created_at`은 실제 저장 시각을 나타내는 UTC ISO timestamp입니다. 같은 시각으로 여러 번 분석해도 UUID로 구분됩니다. 결과가 없는 실행도 `trend_runs`에 기록됩니다.

가장 최근 실행의 결과를 조회합니다. 해당 실행의 결과가 비어 있으면 0행을 반환합니다.

```sql
SELECT rank, keyword, score, post_refs_json
FROM trend_results
WHERE run_id = (
    SELECT run_id FROM trend_runs ORDER BY created_at DESC, rowid DESC LIMIT 1
)
ORDER BY rank;
```

설정과 전체 결과를 재확인하려면:

```sql
SELECT run_id, analysis_at, created_at, report_json
FROM trend_runs
ORDER BY created_at DESC, rowid DESC
LIMIT 1;
```

`post_refs_json`에는 실제 분석에서 후보가 등장한 최근 게시물의 `community`와 `idx`가 들어갑니다. 과거 게시물을 부분 문자열로 검색한 목록이 아닙니다. 이전 실행의 참조 목록도 변경하지 않습니다.

## 문제 해결

| 증상 | 확인할 사항 |
| --- | --- |
| 결과가 비어 있음 | 최근·배경 구간 모두에 데이터가 있는지, 조회수와 커뮤니티 조건이 충족되는지 확인합니다. `recent_posts`와 `background_posts`도 확인하세요. |
| 과거 DB로 실행하면 최근 구간이 비어 있음 | 데이터 기간에 맞는 `--at`을 지정합니다. |
| `No module named trending_keywords` | 현재 Python 환경에서 `python -m pip install .`을 실행합니다. |
| `posts table is missing columns` | 연결한 DB의 `posts` 스키마와 필수 열을 확인합니다. |
| `unable to open database file` | 파일 경로, 읽기 권한, WAL 관련 파일 접근 권한을 확인합니다. |
| 시간대 오류 | 모든 시각을 같은 기준으로 변환하고 오프셋 없는 값으로 전달합니다. |
| 예상한 긴 키워드가 안 나옴 | 토큰 분리 결과, NPMI, 최소 문서 수, 포함 관계 제거 조건을 확인합니다. |

원본 입력과 출력 파일 경로가 같으면 실행을 거부합니다. `--output`에 다른 기존 파일을 지정하면 그 파일을 교체하므로 결과 전용 경로를 사용하세요.
