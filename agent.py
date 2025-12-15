from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command, RetryPolicy
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage

llm = ChatOpenAI(model="gpt-5-nano")

class MyState(TypedDict):
    row_idx: int
    csv_path: str
    command_to_test: str

def generate_command(state):
    out = llm.invoke('generate this command')
    print("got output", out)
    state['row_idx'] += 1
    return {
        "command_to_test": out
    }

workflow = StateGraph(MyState)
workflow.add_node("generate_command", generate_command)

workflow.add_edge(START, "generate_command")
workflow.add_edge("generate_command", END)

agent = workflow.compile()

agent.invoke({"row_idx": 0})


    