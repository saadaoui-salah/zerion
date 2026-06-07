"""CLI commands for the /benchmark system."""

from __future__ import annotations

import json
import asyncio
from typing import TYPE_CHECKING

from rich.text import Text
from rich.table import Table
from rich.panel import Panel

if TYPE_CHECKING:
    from zerion_core.cli.app import ZerionApp


def register_benchmark_commands(app: "ZerionApp") -> None:
    """Register /benchmark commands with the app's command registry."""
    app._commands.register(
        "benchmark",
        "Skill benchmarking and performance evaluation",
        usage="/benchmark leaderboard|report|compare|health|failures|workflow|consolidate|ab_test",
        subcommands=[
            "leaderboard", "report", "compare", "health", "failures",
            "workflow", "consolidate", "ab_test", "skill_report",
        ],
    )


def handle_benchmark_command(app: "ZerionApp", args: list[str]) -> None:
    """Handle /benchmark subcommands."""
    plog = app.query_one("#pipeline-log")

    if not args:
        plog.write("[dim]Usage: /benchmark <subcommand> [args][/]")
        plog.write("[dim]Subcommands: leaderboard, report, compare, health, failures, workflow, consolidate, ab_test, skill_report[/]")
        return

    action = args[0]
    rest = args[1:]

    if action == "leaderboard":
        asyncio.ensure_future(_benchmark_leaderboard(app, rest))

    elif action == "report":
        if not rest:
            plog.write("[red]Usage: /benchmark report <project_id>[/]")
            return
        asyncio.ensure_future(_benchmark_project_report(app, rest[0]))

    elif action == "skill_report":
        if not rest:
            plog.write("[red]Usage: /benchmark skill_report <skill_id> [project_id][/]")
            return
        skill_id = rest[0]
        project_id = rest[1] if len(rest) > 1 else ""
        asyncio.ensure_future(_benchmark_skill_report(app, skill_id, project_id))

    elif action == "compare":
        if not rest:
            plog.write("[red]Usage: /benchmark compare <skill1> <skill2> [skill3...] [/]")
            return
        asyncio.ensure_future(_benchmark_compare(app, rest))

    elif action == "health":
        if not rest:
            plog.write("[red]Usage: /benchmark health <project_id>[/]")
            return
        asyncio.ensure_future(_benchmark_health(app, rest[0]))

    elif action == "failures":
        skill_id = rest[0] if rest else ""
        asyncio.ensure_future(_benchmark_failures(app, skill_id))

    elif action == "workflow":
        asyncio.ensure_future(_benchmark_workflows(app))

    elif action == "consolidate":
        days = int(rest[0]) if rest else 30
        asyncio.ensure_future(_benchmark_consolidate(app, days))

    elif action == "ab_test":
        if len(rest) < 2:
            plog.write("[red]Usage: /benchmark ab_test <skill_a> <skill_b>[/]")
            return
        asyncio.ensure_future(_benchmark_ab_test(app, rest[0], rest[1]))

    else:
        plog.write(f"[red]Unknown subcommand: {action}[/]")


async def _benchmark_leaderboard(app: "ZerionApp", args: list[str]) -> None:
    """Show skill leaderboard."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        project_id = args[0] if args else None
        entries = bm.get_leaderboard(project_id=project_id, limit=15)

        if not entries:
            plog.write("[dim]No benchmark data yet. Skills need to complete tasks to appear here.[/]")
            return

        table = Table(title="Skill Leaderboard", show_header=True, header_style="bold cyan")
        table.add_column("Rank", style="bold", width=6)
        table.add_column("Skill", style="bold")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Tasks", justify="right")
        table.add_column("Success", justify="right")
        table.add_column("Trend", justify="center")

        for entry in entries:
            trend_style = {
                "improving": "[green]+[/]",
                "declining": "[red]-[/]",
                "stable": "[dim]=[/]",
            }.get(entry.trend, "[dim]?[/]")

            table.add_row(
                str(entry.rank),
                entry.skill_id,
                f"{entry.score:.1f}",
                str(entry.tasks_completed),
                f"{entry.success_rate:.0%}",
                trend_style,
            )

        plog.write(table)

    except Exception as e:
        plog.write(f"[red]Leaderboard error: {e}[/]")


async def _benchmark_project_report(app: "ZerionApp", project_id: str) -> None:
    """Show project health report."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        health = bm.get_project_health(project_id)

        panel_content = []
        panel_content.append(f"[bold]Project:[/] {project_id}")
        panel_content.append(f"[bold]Total Executions:[/] {health['total_executions']}")
        panel_content.append(f"[bold]Skills Used:[/] {health['skills_used']}")
        panel_content.append(f"[bold]Success Rate:[/] {health['overall_success_rate']:.1%}")
        panel_content.append(f"[bold]Best Skill:[/] [green]{health['best_performing_skill']}[/]")
        panel_content.append(f"[bold]Worst Skill:[/] [red]{health['worst_performing_skill']}[/]")
        panel_content.append(f"[bold]Regression Trend:[/] {health['regression_trend']}")

        if health.get("failure_breakdown"):
            panel_content.append("\n[bold]Failure Breakdown:[/]")
            for ftype, count in health["failure_breakdown"].items():
                panel_content.append(f"  {ftype}: {count}")

        panel = Panel(
            "\n".join(panel_content),
            title=f"Project Health: {project_id}",
            border_style="blue",
        )
        plog.write(panel)

    except Exception as e:
        plog.write(f"[red]Report error: {e}[/]")


async def _benchmark_skill_report(
    app: "ZerionApp", skill_id: str, project_id: str
) -> None:
    """Show detailed skill report."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        report = bm.get_skill_report(skill_id, project_id)

        panel_content = []
        panel_content.append(f"[bold]Skill:[/] {skill_id}")
        if project_id:
            panel_content.append(f"[bold]Project:[/] {project_id}")
        panel_content.append(f"[bold]Total Executions:[/] {report['total_executions']}")
        panel_content.append(f"[bold]Avg Duration:[/] {report['avg_duration_ms']:.0f}ms")
        panel_content.append(f"[bold]Test Pass Rate:[/] {report['test_pass_rate']:.1%}")
        panel_content.append(f"[bold]Success Rate:[/] {report['success_rate']:.1%}")
        panel_content.append(f"[bold]Build Success Rate:[/] {report['build_success_rate']:.1%}")
        panel_content.append(f"[bold]Regression Rate:[/] {report['regression_rate']:.1%}")
        panel_content.append(f"[bold]Composite Score:[/] {report['composite_score']:.1f}")
        panel_content.append(f"[bold]Reputation:[/] {report['reputation']:.1f}")
        panel_content.append(f"[bold]Reputation Trend:[/] {report['reputation_trend']}")
        panel_content.append(f"[bold]Total Failures:[/] {report['total_failures']}")
        panel_content.append(f"[bold]Top Task Type:[/] {report['top_task_type']}")

        panel = Panel(
            "\n".join(panel_content),
            title=f"Skill Report: {skill_id}",
            border_style="green",
        )
        plog.write(panel)

        # Show task distribution
        if report.get("task_distribution"):
            dist_table = Table(title="Task Distribution", show_header=True)
            dist_table.add_column("Task Type")
            dist_table.add_column("Count", justify="right")
            for tt, count in report["task_distribution"].items():
                dist_table.add_row(tt, str(count))
            plog.write(dist_table)

    except Exception as e:
        plog.write(f"[red]Skill report error: {e}[/]")


async def _benchmark_compare(app: "ZerionApp", skill_ids: list[str]) -> None:
    """Compare multiple skills."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        results = bm.compare_skills(skill_ids)

        table = Table(title="Skill Comparison", show_header=True, header_style="bold cyan")
        table.add_column("Skill", style="bold")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Test Rate", justify="right")
        table.add_column("Build Rate", justify="right")
        table.add_column("Patch Accept", justify="right")
        table.add_column("Samples", justify="right")

        for r in results:
            table.add_row(
                r.get("skill_id", ""),
                f"{r.get('total_score', 0):.1f}",
                f"{r.get('test_pass_rate', 0):.0%}",
                f"{r.get('build_success_rate', 0):.0%}",
                f"{r.get('patch_acceptance_rate', 0):.0%}",
                str(r.get("sample_count", 0)),
            )

        plog.write(table)

    except Exception as e:
        plog.write(f"[red]Comparison error: {e}[/]")


async def _benchmark_health(app: "ZerionApp", project_id: str) -> None:
    """Alias for project report."""
    await _benchmark_project_report(app, project_id)


async def _benchmark_failures(app: "ZerionApp", skill_id: str) -> None:
    """Show failure analysis."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        failures = bm.failure_analyzer.get_failures(
            skill_id=skill_id if skill_id else None, limit=20
        )

        if not failures:
            plog.write("[dim]No failures recorded.[/]")
            return

        table = Table(title="Recent Failures", show_header=True, header_style="bold red")
        table.add_column("Skill", style="bold")
        table.add_column("Type")
        table.add_column("Root Cause", max_width=40)
        table.add_column("Time")

        for f in failures:
            table.add_row(
                f.skill_id,
                f.failure_type,
                f.root_cause[:40] if f.root_cause else "-",
                f.timestamp[:19],
            )

        plog.write(table)

        # Show recommendations
        if skill_id:
            recs = bm.get_failure_recommendations(skill_id)
            if recs:
                plog.write("\n[bold]Recommendations:[/]")
                for rec in recs:
                    plog.write(f"  [yellow]-[/] {rec}")

    except Exception as e:
        plog.write(f"[red]Failure analysis error: {e}[/]")


async def _benchmark_workflows(app: "ZerionApp") -> None:
    """Show workflow benchmarks."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        workflows = bm.workflow_bench.get_all_workflows()

        if not workflows:
            plog.write("[dim]No workflow benchmarks yet.[/]")
            return

        table = Table(title="Workflow Benchmarks", show_header=True, header_style="bold cyan")
        table.add_column("Workflow", style="bold")
        table.add_column("Score", justify="right", style="green")
        table.add_column("Success Rate", justify="right")
        table.add_column("Avg Time", justify="right")
        table.add_column("Regressions", justify="right")
        table.add_column("Runs", justify="right")

        for wf in workflows[:15]:
            table.add_row(
                wf.workflow_name,
                f"{wf.score:.2f}",
                f"{wf.success_rate:.0%}",
                f"{wf.avg_time_ms:.0f}ms",
                f"{wf.regression_rate:.0%}",
                str(wf.total_runs),
            )

        plog.write(table)

    except Exception as e:
        plog.write(f"[red]Workflow error: {e}[/]")


async def _benchmark_consolidate(app: "ZerionApp", days: int) -> None:
    """Run benchmark consolidation."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        count = bm.run_consolidation(older_than_days=days)
        plog.write(f"[green]Consolidated {count} skill benchmark periods (older than {days} days)[/]")

    except Exception as e:
        plog.write(f"[red]Consolidation error: {e}[/]")


async def _benchmark_ab_test(
    app: "ZerionApp", skill_a: str, skill_b: str
) -> None:
    """Show A/B test results between two skills."""
    plog = app.query_one("#pipeline-log")
    try:
        await app.orchestrator.init_benchmark()
        bm = app.orchestrator._benchmark

        result = bm.get_head_to_head(skill_a, skill_b)

        if result["total_tests"] == 0:
            plog.write(f"[dim]No A/B tests found between {skill_a} and {skill_b}[/]")
            return

        panel_content = []
        panel_content.append(f"[bold]Skill A:[/] {skill_a}")
        panel_content.append(f"[bold]Skill B:[/] {skill_b}")
        panel_content.append(f"[bold]Total Tests:[/] {result['total_tests']}")
        panel_content.append(f"[bold]{skill_a} Wins:[/] [green]{result['skill_a_wins']}[/]")
        panel_content.append(f"[bold]{skill_b} Wins:[/] [green]{result['skill_b_wins']}[/]")
        panel_content.append(f"[bold]Ties:[/] {result['ties']}")
        panel_content.append(f"[bold]Avg Score {skill_a}:[/] {result['avg_score_a']:.2f}")
        panel_content.append(f"[bold]Avg Score {skill_b}:[/] {result['avg_score_b']:.2f}")

        panel = Panel(
            "\n".join(panel_content),
            title=f"A/B Test: {skill_a} vs {skill_b}",
            border_style="yellow",
        )
        plog.write(panel)

    except Exception as e:
        plog.write(f"[red]A/B test error: {e}[/]")
