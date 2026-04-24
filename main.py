import re
import sys
from pathlib import Path
from anthropic import Anthropic
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import print as rprint

client = Anthropic()
console = Console()

SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 
             'dist', 'build', '.next', 'target'}
SKIP_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', 
                   '.lock', '.sum', '.pyc'}
MAX_FILE_SIZE = 50_000

def collect_files(directory: str) -> str:
    root = Path(directory)
    output = []
    total_chars = 0
    MAX_TOTAL = 80_000

    for path in sorted(root.rglob('*')):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if not path.is_file():
            continue
        if path.suffix in SKIP_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_SIZE: 
            continue

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            relative = path.relative_to(root)
            entry = f"### FILE: {relative}\n{content}\n"
            if total_chars + len(entry) > MAX_TOTAL:
                output.append("### NOTE: Codebase truncated due to size limit.\n")
                break
            output.append(entry)
            total_chars += len(entry)
        except Exception:
            continue
    return '\n'.join(output)

def get_explanation(code: str) -> str:
    console.print("\n[bold cyan]Analyzing codebase...[/bold cyan]")
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": code,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": """You are a coding instructor. A student used AI to generate this codebase and needs to understand it.

Explain the following in markdown:
1. **Architecture Overview** - What was built, what problem it solves, how it's structured
2. **Key Components** - Each important file/module, what it does, why it exists, how it connects
3. **Core Concepts** - Patterns and techniques used that the student should understand
4. **How It All Connects** - Data flow from entry point to output"""
                }
            ]
        }]
    )
    return response.content[0].text


def get_quiz_questions(code: str) -> list[str]:
    console.print("\n[bold cyan]Generating quiz questions...[/bold cyan]")
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": code,
                    "cache_control": {"type": "ephemeral"}
                },
                {
                    "type": "text",
                    "text": """Generate exactly 5 quiz questions to test a student's understanding of this codebase.
Questions should test real understanding, not just reading comprehension.

Return ONLY the 5 questions, one per line, numbered like:
1. [question]
2. [question]
3. [question]
4. [question]
5. [question]"""
                }
            ]
        }]
    )
    
    questions = []
    for line in response.content[0].text.strip().split('\n'):
        line = line.strip()
        if line and line[0].isdigit() and '.' in line:
            question = line.split('.', 1)[1].strip()
            if question:
                questions.append(question)
    return questions

def run_quiz(questions: list[str], full_code: str):
    console.print(Panel("[bold yellow]Time to prove you understood it[/bold yellow]", 
                       border_style="yellow"))
    
    answers = []
    for i, question in enumerate(questions, 1):
        console.print(f"\n[bold]Q{i}:[/bold] {question}")
        answer = input("Your answer: ").strip()
        answers.append((question, answer))

    console.print("\n[bold cyan]Evaluating your answers...[/bold cyan]")

    qa_text = '\n'.join([f"Q{i+1}: {q}\nAnswer: {a}" 
                          for i, (q, a) in enumerate(answers)])

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": full_code,
                    "cache_control": {"type": "ephemeral"}
                },
                 {
                    "type": "text",
                    "text": f"""A student reviewed this codebase and answered these quiz questions.

Grade each answer using this exact format:

**Q[N]: [topic]**
Score: X/3
What you got right: ...
What you missed: ...
Ideal answer: ...

Be direct and accurate. Don't be encouraging for its own sake. If the answer is wrong, say so and explain why.

Student answers:
{qa_text}

End with a brief summary of overall understanding and what to revisit."""
                }
           ]
        }]
    )

    console.print(Panel(
        Markdown(response.content[0].text),
        title="[bold]Results[/bold]",
        border_style="green"
    ))

def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python main.py <directory>[/red]")
        sys.exit(1)

    directory = sys.argv[1]
    
    if not Path(directory).exists():
        console.print(f"[red]Directory not found: {directory}[/red]")
        sys.exit(1)

    console.print(Panel(f"[bold]CodeLearn[/bold]\nAnalyzing: {directory}", 
                       border_style="cyan"))

    explain_only = '--explain-only' in sys.argv
    explain_only = '--explain-only' in sys.argv
    code = collect_files(directory)
    
    if not code.strip():
        console.print("[red]No readable code files found.[/red]")
        sys.exit(1)

    explanation = get_explanation(code)
    questions = get_quiz_questions(code)

    console.print(Panel(
        Markdown(explanation),
        title="[bold]Codebase Breakdown[/bold]",
        border_style="cyan"
    ))

    if questions and not explain_only:
        input("\n[Press Enter when you're ready for the quiz]")
        run_quiz(questions, code)
    elif explain_only:
        console.print("\n[bold cyan]Explain-only mode — skipping quiz.[/bold cyan]")
    else:
        console.print("[yellow]No quiz questions were generated.[/yellow]")


if __name__ == "__main__":
    main()
