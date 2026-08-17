"""검수된 QA 몇 건을 넣어 서비스가 실제로 답하는지 확인한다.

QA 인덱스가 비면 모든 질문이 `unresolved` 로 떨어져서 "동작은 하는데 아무것도 안 나오는"
상태가 된다. 화면·배포를 점검할 때 그게 버그인지 데이터가 없는 건지 구분이 안 되므로
최소한의 시드를 둔다. 실제 답변은 스튜디오에서 생성 후 검수해 채운다.

    python scripts/seed_demo_qa.py [--force]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ingestion.doc_index import DocIndex   # noqa: E402
from app.qa import store as qa_store           # noqa: E402
from app.qa.index import QaIndex               # noqa: E402

DEMO = [
    {
        "question": "API 등록은 어떻게 하나요?",
        "category_id": "api_reg_flow",
        "source_doc_ids": ["api-등록"],
        "variants": [
            "API를 처음 등록하려면 무엇부터 해야 하나요?",
            "API 등록 절차 알려주세요",
            "새 API를 만들고 싶습니다",
            "API 등록하는 방법",
        ],
        "answer": (
            "**API 그룹(SPC)** 을 먼저 만든 뒤 'API 등록' 화면에서 등록을 진행합니다.\n\n"
            "1. API Manager > **API 그룹** 메뉴에서 그룹을 등록합니다.\n"
            "2. `API 등록` 화면에서 방금 만든 그룹을 선택합니다.\n"
            "3. 서비스 URI · 운영 URI · 권한그룹을 입력하고 저장합니다.\n\n"
            "- 권한그룹을 비워두면 내부 관리자만 호출할 수 있습니다.\n"
            "- 저장 후 **운영 반영**을 해야 운영 환경에서 호출됩니다."
        ),
    },
    {
        "question": "권한그룹은 무엇을 선택해야 하나요?",
        "category_id": "api_reg_field",
        "source_doc_ids": ["api-등록-필드설명"],
        "variants": [
            "권한그룹 뭐 골라요?",
            "권한그룹 선택 기준이 궁금합니다",
            "권한그룹은 무엇을 뜻하나요?",
            "권한그룹 값을 어디서 확인하나요?",
        ],
        "answer": (
            "권한그룹은 **이 API를 호출할 수 있는 사용자 묶음**입니다.\n\n"
            "- 사전에 `인증·권한` 메뉴에서 만들어 둔 권한그룹만 선택할 수 있습니다.\n"
            "- 비워두면 내부 관리자만 호출할 수 있는 상태로 저장됩니다.\n"
            "- 외부 파트너가 호출해야 한다면 해당 파트너가 속한 권한그룹을 지정합니다."
        ),
    },
    {
        "question": "템플릿을 수정하면 기존 API에도 반영되나요?",
        "category_id": "tmplt_edit",
        "source_doc_ids": ["템플릿-관리"],
        "variants": [
            "템플릿 수정 시 기존 API 영향",
            "템플릿을 고치면 이미 등록한 API는 어떻게 되나요?",
        ],
        "answer": (
            "반영됩니다. 해당 템플릿을 참조하는 모든 API의 **다음 호출부터** 적용됩니다.\n\n"
            "- 이미 진행 중인 호출에는 영향을 주지 않습니다.\n"
            "- 변경 이력은 템플릿 상세 화면의 `이력` 탭에서 확인할 수 있습니다."
        ),
    },
    {
        # 출처 문서에 **도식(SVG)** 이 들어 있는 건이다. 답변은 텍스트로 두고 그림은 문서에만
        # 둔다는 원칙을 실제로 보여주는 자리라, 화면 시연에서 이 질문을 쓴다.
        "question": "가입 절차가 어떻게 되나요?",
        "category_id": "auth_apply",
        "source_doc_ids": ["가입-절차-흐름도"],
        "variants": [
            "가입은 어떻게 하나요?",
            "회원가입하고 나서 뭘 해야 하나요?",
            "가입했는데 메뉴가 안 보입니다",
            "API 등록하려면 어떤 절차를 밟아야 하나요?",
            "권한 신청은 언제 하나요?",
            "승인은 났다는데 화면이 그대로입니다",
        ],
        "answer": (
            "가입만으로는 끝나지 않습니다. **권한 신청과 승인**까지 마쳐야 등록·배포 메뉴가 열립니다.\n\n"
            "1. 회원가입을 합니다.\n"
            "2. 로그인합니다.\n"
            "3. 마이페이지에서 필요한 시스템의 **권한그룹을 신청**합니다.\n"
            "4. 관리자 승인을 기다립니다. 자동 승인이 아니라 사람이 직접 처리합니다.\n"
            "5. 승인 뒤 **로그아웃했다가 다시 로그인**합니다.\n\n"
            "- 5번을 건너뛰면 승인이 나도 화면이 그대로입니다. 권한 정보가 로그인 시점 값으로 "
            "세션에 담기기 때문이며, 새로고침으로는 바뀌지 않습니다.\n"
            "- 권한 신청은 **시스템 단위**입니다. 여러 시스템이 필요하면 각각 신청합니다.\n"
            "- 전체 흐름은 출처 문서의 그림에서 한눈에 볼 수 있습니다."
        ),
    },
]


def main() -> int:
    if qa_store.load_qa() and "--force" not in sys.argv:
        print("QA 인덱스에 이미 항목이 있습니다. 덮어쓰려면 --force 를 주세요.")
        return 0

    print("문서 색인 중…")
    docs = DocIndex().ingest_dir(force=True)
    print(f"  문서 {len(docs)}건 / 청크 {sum(docs.values())}개")

    index = QaIndex()
    vectors = 0
    for spec in DEMO:
        item = qa_store.upsert_item(qa_store.QaItem(
            qa_id=qa_store.new_qa_id(), status="approved", created_by="human", **spec,
        ))
        vectors += index.upsert_item(item)

    print(f"QA {len(DEMO)}건 / 검색 벡터 {vectors}개를 넣었습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
