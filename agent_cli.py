from datetime import date
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from tools import (
    collection,
    search_runwise_knowledge,
    get_intervals_activities,
    get_activity_intervals_detail,
    get_intervals_wellness,
    get_planned_workouts,
    schedule_intervals_workout,
)

load_dotenv()
console = Console()

# 1. Pré-chauffer ChromaDB au lancement pour ne pas bloquer pendant la conversation
with console.status("[bold cyan]Initialisation de ChromaDB (RunWise)...[/bold cyan]"):
    nb_chunks = collection.count()
    if nb_chunks > 0:
        collection.query(query_texts=["test"], n_results=1)
console.print(f"[green]✅ Base RunWise prête ({nb_chunks} segments en mémoire)[/green]")

# 2. Initialisation de Gemini avec timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
    temperature=0.2,
    timeout=30,
)

TODAY = date.today().isoformat()

SYSTEM_PROMPT = f"""Tu es un coach de course à pied expert. Nous sommes aujourd'hui le {TODAY}.
Tu t'appuies sur :
1. La philosophie scientifique et terrain du 'RunWise Podcast' (via search_runwise_knowledge).
2. Les données réelles de l'athlète sur Intervals.icu (séances, tours/laps, wellness CTL/ATL/TSB, calendrier).

Règles :
- Cite TOUJOURS l'épisode RunWise, le timestamp (MM:SS) et le lien YouTube quand tu t'appuies sur une vidéo.
- Quand on te demande d'analyser une séance précise, appelle d'abord get_intervals_activities pour trouver son ID, puis get_activity_intervals_detail(activity_id) pour voir les laps.
- Sois précis sur les chiffres (allures au km, dérive cardiaque, charge CTL/ATL).
"""

agent = create_react_agent(
    model=llm,
    tools=[
        search_runwise_knowledge,
        get_intervals_activities,
        get_activity_intervals_detail,
        get_intervals_wellness,
        get_planned_workouts,
        schedule_intervals_workout,
    ],
    prompt=SYSTEM_PROMPT,
)

def main():
    console.print(f"[bold green]🏃‍♂️ RunWise x Intervals.icu CLI ({TODAY}) — Tape 'q' pour quitter[/bold green]\n")
    messages = []

    while True:
        try:
            user_input = console.input("[bold cyan]Toi > [/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            break
        if user_input.strip().lower() in ["q", "quit", "exit"]:
            break
        if not user_input.strip():
            continue

        messages.append(("user", user_input))
        final_answer = ""

        # Streaming étape par étape : affiche les appels d'outils en direct !
        with console.status("[bold yellow]🤖 Réflexion de l'agent...[/bold yellow]") as status:
            for step in agent.stream({"messages": messages}, stream_mode="updates"):
                for node_name, node_data in step.items():
                    new_msgs = node_data.get("messages", [])
                    for msg in new_msgs:
                        messages.append(msg)
                        # Si le modèle décide d'appeler un outil, on l'affiche tout de suite
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                console.print(f"[bold cyan]  ⚡ Appel en cours :[/bold cyan] [yellow]{tc['name']}({tc['args']})[/yellow]")
                                status.update(f"[bold yellow]Exécution de {tc['name']}...[/bold yellow]")
                        # Si un outil vient de répondre, on confirme sa réception
                        elif msg.type == "tool":
                            console.print(f"[dim green]  ✔ Données reçues de {msg.name} ({len(str(msg.content))} caractères)[/dim green]")
                            status.update("[bold yellow]✍️  Synthèse de la réponse par Gemini...[/bold yellow]")
                        # Si c'est la réponse finale du modèle
                        elif msg.type == "ai" and msg.content:
                            if isinstance(msg.content, list):
                                final_answer = "\n".join(p.get("text", "") for p in msg.content if isinstance(p, dict))
                            else:
                                final_answer = str(msg.content)

        console.print("\n[bold magenta]Coach RunWise >[/bold magenta]")
        console.print(Markdown(final_answer))
        console.print("[dim]" + "─" * 70 + "[/dim]\n")

if __name__ == "__main__":
    main()
