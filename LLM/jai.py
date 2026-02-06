import os
import json
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader
from pydantic import BaseModel, Field
from openai import pydantic_function_tool


# =============================
# CONFIG
# =============================
MODEL = "gpt-4o-mini"
MAX_QNA_PAIRS = 5

# Force .env to override everything
load_dotenv(override=True)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)

# =============================
# LOAD LINKEDIN PDF
# =============================
reader = PdfReader("/Users/jg/projects/ecameo/LLM/Me/linkedin.pdf")
linkedin = ""
for page in reader.pages:
    text = page.extract_text()
    if text:
        linkedin += text + "\n"

# =============================
# LOAD TEXTUAL INFO
# =============================
with open("/Users/jg/projects/ecameo/Me/summary.txt", "r") as f:
    summary = f.read()

# =============================
# SYSTEM PROMPT
# =============================
# SYSTEM_PROMPT = f"""
# You are an AI assistant answering on behalf of Jai Goswami.

# You are to strictly answer questions that you have clear answers to, no guess work is allowed.
# If you do not have exact answer to a question do not hallucinate or produce any answer that you think might fit ask the user to contact me or ask them for their email and share their question using the to

# Name: Jai Goswami

# LinkedIn Information:
# {linkedin}

# Additional Textual Information:
# {textual_info}

# ROLE & TONE
# - Answer in first person ("I")
# - Be concise, technical, honest

# KNOWLEDGE SCOPE
# - Only use this prompt and last 5 QnA pairs
# - Do not hallucinate

# ESCALATION RULES
# - If unsure, ask to get back via email
# - Use tools when appropriate

# TOOLS
# - get_answer_later
# - contact_me
# """
name ="Jai Goswami"

system_prompt = f"You are acting as {name}. You are answering questions on {name}'s website, \
particularly questions related to {name}'s career, background, skills and experience. \
Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
You are given a summary of {name}'s background and LinkedIn profile which you can use to answer questions. \
Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
If you don't know the answer, say so."

system_prompt += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
system_prompt += f"With this context, please chat with the user, always staying in character as {name}."
system_prompt += f"you are strictly not to answer questions that are not related to {name}'s career, background, skills and experience, in such cases you should say that you can only answer questions related to {name}'s career, background, skills and experience."


# =============================
# TOOL SCHEMAS
# =============================
# =============================
# TOOL DEFINITIONS (Responses API compatible)
# =============================

class GetAnswerLater(BaseModel):
    user_email: str = Field(..., description="Email address provided by the user")
    question: str = Field(..., description="The unanswered user question")
    conversation_summary: str = Field(..., description="Summary of the last 5 QnAs")


class ContactMe(BaseModel):
    user_email: str = Field(..., description="User's email address")
    reason: str = Field(..., description="Why the user wants to get in touch")
    conversation_summary: str = Field(..., description="Summary of the last 5 QnAs")


TOOLS = [
    pydantic_function_tool(GetAnswerLater),
    pydantic_function_tool(ContactMe),
]

# =============================
# SESSION MEMORY
# =============================
class SessionMemory:
    def __init__(self):
        self.messages: List[Dict] = []

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-MAX_QNA_PAIRS * 2 :]

    def get(self):
        return self.messages

    def summary(self):
        out = []
        for i in range(0, len(self.messages), 2):
            q = self.messages[i]["content"]
            a = self.messages[i + 1]["content"]
            out.append(f"Q: {q}\nA: {a}")
        return "\n".join(out)

# =============================
# STREAMING CHAT
# =============================
def stream_chat(session: SessionMemory, user_input: str):
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(session.get())
    messages.append({"role": "user", "content": user_input})

    stream = client.responses.stream(
        model=MODEL,
        input=messages,
        tools=TOOLS,
    )

    full_response = ""
    tool_call = None

    with stream as s:
        for event in s:
            if event.type == "response.output_text.delta":
                print(event.delta, end="", flush=True)
                full_response += event.delta

            elif event.type == "response.tool_call":
                tool_call = event
                break

    print()
    return full_response.strip(), tool_call


# =============================
# TOOL HANDLER
# =============================
def handle_tool(tool_call, session: SessionMemory):
    args = json.loads(tool_call.arguments)
    payload = {
        "tool": tool_call.name,
        "data": args,
    }

    print("\n--- TOOL PAYLOAD ---")
    print(payload)
    print("--------------------\n")

# =============================
# MAIN LOOP
# =============================
def main():
    session = SessionMemory()

    while True:
        user_input = input("\nUser: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        response, tool_call = stream_chat(session, user_input)

        if tool_call:
            handle_tool(tool_call, session)
        else:
            session.add("user", user_input)
            session.add("assistant", response)

if __name__ == "__main__":
    main()