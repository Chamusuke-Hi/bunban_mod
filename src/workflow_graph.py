"""LangGraphで実行・承認・却下フローを管理する。"""

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from .agent import run
from .experience import (
    approve_pending_experience,
    reject_pending_experience,
    list_approved_experiences_for_display,
    load_experiences,
)


class WorkflowState(TypedDict, total=False):
    action: Literal["run", "list-approved"]
    user_input: str
    use_experience: bool
    result: str
    approved: bool  # confirm ノードの判定結果


def _check_experience_node(state: WorkflowState) -> WorkflowState:
    """承認済み経験を検索し、使用するか対話的に確認する。"""
    print("[LangGraph] ノード: check_experience - 開始")
    
    use_exp = bool(state.get("use_experience", False))
    
    if use_exp:
        print("  経験参照: 有効（フラグ指定済み）")
    else:
        approved = load_experiences(max_count=5)
        if approved:
            print(f"\n【使用可能な承認済み経験】 {len(approved)}件見つかりました")
            for i, exp in enumerate(approved, 1):
                ts = exp.get("timestamp", "")
                inp = exp.get("user_input", "")[:60]
                tools_used = len(exp.get("tool_trace", []))
                print(f"  {i}. [{ts}] {inp}  (ツール{tools_used}回)")
            choice = input("\n過去の経験を参照しますか? (y=参照 / n=使わない): ").strip().lower()
            if choice in {"y", "yes"}:
                use_exp = True
                print("✓ 経験参照を有効にします")
            else:
                print("→ 経験なしで自律計画します")
        else:
            print("  承認済み経験なし → 初回実行として進めます")
    
    print("[LangGraph] ノード: check_experience - 終了\n")
    return {"use_experience": use_exp}


def _run_node(state: WorkflowState) -> WorkflowState:
    print("\n[LangGraph] ノード: run - 開始")
    
    result = run(
        user_input=state.get("user_input") or None,
        use_experience=bool(state.get("use_experience", False)),
    )
    print("[LangGraph] ノード: run - 終了\n")
    return {"result": result}


def _confirm_node(state: WorkflowState) -> WorkflowState:
    """実行結果を表示し、承認/却下を対話的に確認する。"""
    print("[LangGraph] ノード: confirm - 開始")
    print("\n" + "=" * 60)
    print("【実行結果】")
    print("=" * 60)
    print(state.get("result", ""))
    print("=" * 60)
    
    choice = input("\nこの結果を承認しますか? (y=承認 / n=却下): ").strip().lower()
    approved = choice in {"y", "yes"}
    print(f"[LangGraph] ノード: confirm - 終了 ({'承認' if approved else '却下'})\n")
    return {"approved": approved}


def _approve_node(state: WorkflowState) -> WorkflowState:
    print("[LangGraph] ノード: approve - 開始")
    path = approve_pending_experience()
    msg = f"✓ 承認しました → {path}" if path else "承認対象が見つかりません"
    print(f"[LangGraph] ノード: approve - 終了\n")
    return {"result": msg}


def _reject_node(state: WorkflowState) -> WorkflowState:
    print("[LangGraph] ノード: reject - 開始")
    path = reject_pending_experience()
    msg = f"✗ 却下しました（削除）: {path}" if path else "却下対象が見つかりません"
    print(f"[LangGraph] ノード: reject - 終了\n")
    return {"result": msg}


def _list_approved_node(state: WorkflowState) -> WorkflowState:
    print("[LangGraph] ノード: list-approved - 開始")
    listing = list_approved_experiences_for_display()
    print(f"[LangGraph] ノード: list-approved - 終了\n")
    return {"result": listing}


def _route_entry(state: WorkflowState) -> str:
    action = state.get("action", "run")
    if action == "list-approved":
        return "list-approved"
    return "run"


def _route_after_confirm(state: WorkflowState) -> str:
    """confirm の結果に基づいて approve / reject に分岐。"""
    if state.get("approved"):
        return "approve"
    return "reject"


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("check_experience", _check_experience_node)
    graph.add_node("run", _run_node)
    graph.add_node("confirm", _confirm_node)
    graph.add_node("approve", _approve_node)
    graph.add_node("reject", _reject_node)
    graph.add_node("list-approved", _list_approved_node)

    # エントリポイント: check_experience → run or list-approved
    graph.set_conditional_entry_point(
        _route_entry,
        {
            "run": "check_experience",
            "list-approved": "list-approved",
        },
    )

    # check_experience → run → confirm → approve/reject → END
    graph.add_edge("check_experience", "run")
    graph.add_edge("run", "confirm")
    graph.add_conditional_edges(
        "confirm",
        _route_after_confirm,
        {
            "approve": "approve",
            "reject": "reject",
        },
    )

    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    graph.add_edge("list-approved", END)

    return graph.compile()


def execute_workflow(
    action: Literal["run", "list-approved"],
    user_input: str | None = None,
    use_experience: bool = False,
) -> str:
    app = build_workflow()
    state: WorkflowState = {
        "action": action,
        "use_experience": use_experience,
    }
    if user_input:
        state["user_input"] = user_input

    result = app.invoke(state)
    return result.get("result", "結果が取得できませんでした")
