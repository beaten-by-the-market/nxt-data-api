"""시나리오 노트북 빌더: scenarios/_src/<유형>/<이름>.py → scenarios/<유형>/<이름>.ipynb (실행 결과 포함).

원본 형식 (셀 구분 주석)
    # %% [markdown]
    # # 제목
    # 설명 …
    # %%
    파이썬 코드 …

빌더가 하는 일
1. 첫 markdown 셀 아래에 "Colab에서 열기" 배지와 준비 셀 2개를 넣는다.
   - Colab일 때만 패키지 설치 (nxt-data-api·krx-data-api 를 GitHub에서, 한글 폰트)
   - 공통 헬퍼(_tools/nxt_helper.py 내용 그대로)
2. 노트북을 실제로 실행해 출력까지 저장한다(--no-exec 이면 실행 안 함).
   실행 폴더는 레포 루트라서 로컬에서는 이 레포의 nxt_data_api 를 그대로 import 한다.
   krx_data_api 는 설치된 패키지를 쓰고, KRX_ID/KRX_PW 는 환경변수 → 작업 폴더 .env →
   (편집 가능 설치라면) krx-data-api 레포의 .env 순서로 찾는다. 계정 정보는 출력에 남지 않는다.

사용
    python scenarios/_tools/build.py                       # 전체
    python scenarios/_tools/build.py 1_nxt_vs_krx/01       # 경로에 이 문자열이 든 원본만
    python scenarios/_tools/build.py --no-exec …
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.platform.startswith("win"):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

HERE = Path(__file__).resolve().parent
SCEN = HERE.parent
REPO = SCEN.parent
SRC = SCEN / "_src"
GITHUB = "beaten-by-the-market/nxt-data-api"
BRANCH = "main"

INSTALL_CELL = """# Colab에서만: 패키지 설치 (로컬에서는 건너뜀)
import sys
if "google.colab" in sys.modules:
    !pip -q install koreanize-matplotlib \\
        git+https://github.com/beaten-by-the-market/nxt-data-api.git \\
        git+https://github.com/beaten-by-the-market/krx-data-api.git"""


def parse(src: str) -> list[tuple[str, str]]:
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        text = "\n".join(buf).strip("\n")
        if kind == "markdown":
            text = "\n".join(re.sub(r"^# ?", "", ln) for ln in text.splitlines())
        if text.strip():
            cells.append((kind, text))

    for line in src.splitlines():
        if line.startswith("# %%"):
            flush()
            kind, buf = ("markdown" if "[markdown]" in line else "code"), []
        else:
            buf.append(line)
    flush()
    return cells


def build(src_path: Path, execute: bool = True) -> Path:
    rel = src_path.relative_to(SRC).with_suffix(".ipynb")
    out = SCEN / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    cells = parse(src_path.read_text(encoding="utf-8"))
    if not cells or cells[0][0] != "markdown":
        raise SystemExit(f"{src_path}: 첫 셀은 제목 markdown 이어야 합니다")

    url = f"https://colab.research.google.com/github/{GITHUB}/blob/{BRANCH}/scenarios/{quote(rel.as_posix())}"
    badge = f"[![Colab에서 열기](https://colab.research.google.com/assets/colab-badge.svg)]({url})"
    helper = (HERE / "nxt_helper.py").read_text(encoding="utf-8").strip()
    setup_md = ("## 0. 준비\n"
                "넥스트레이드(NXT) 데이터는 로그인이 필요 없지만, KRX 정보데이터시스템은 2026-09부터 로그인해야 합니다. "
                "Colab 왼쪽 🔑(Secrets)에 `KRX_ID`, `KRX_PW`를 등록하고 이 노트북의 액세스를 켠 뒤 "
                "아래 두 셀을 실행하세요. 두 번째 셀은 모든 시나리오에 공통인 헬퍼입니다(접어 두어도 됩니다).")

    nb = nbformat.v4.new_notebook()
    nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                   "language_info": {"name": "python"},
                   "colab": {"provenance": [], "toc_visible": True}}
    nb.cells.append(nbformat.v4.new_markdown_cell(cells[0][1] + "\n\n" + badge))
    nb.cells.append(nbformat.v4.new_markdown_cell(setup_md))
    nb.cells.append(nbformat.v4.new_code_cell(INSTALL_CELL))
    nb.cells.append(nbformat.v4.new_code_cell(helper, metadata={"cellView": "form", "jupyter": {"source_hidden": True}}))
    for kind, text in cells[1:]:
        nb.cells.append(nbformat.v4.new_markdown_cell(text) if kind == "markdown" else nbformat.v4.new_code_cell(text))

    if execute:
        client = NotebookClient(nb, timeout=900, kernel_name="python3",
                                resources={"metadata": {"path": str(REPO)}})
        try:
            client.execute()
        except CellExecutionError as e:
            nbformat.write(nb, out)
            print(f"✗ {rel} — 실행 오류 (오류까지 저장함)\n{str(e)[-1500:]}")
            return out
    nbformat.write(nb, out)
    print(f"✓ {rel}")
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    execute = "--no-exec" not in sys.argv
    srcs = sorted(p for p in SRC.rglob("*.py"))
    if args:
        srcs = [p for p in srcs if any(a in p.relative_to(SRC).as_posix() for a in args)]
    if not srcs:
        raise SystemExit("빌드할 원본이 없습니다")
    for p in srcs:
        build(p, execute)


if __name__ == "__main__":
    main()
