"""Final assembler agent."""

import logging
from typing import Any, Dict

from app.agents.base import BaseAgent
from app.models.claim import Draft
from app.models.document import Document
from app.models.outline import OutlineNode
from app.models.run import Run

logger = logging.getLogger(__name__)


class FinalAssembler(BaseAgent):
    """Agent for assembling final LaTeX document."""

    MODEL = "amazon/nova-2-lite-v1:free"

    def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble final LaTeX document."""
        run_id = payload["run_id"]

        # Load run
        run = self.db.query(Run).filter(Run.run_id == run_id).first()

        # Load outline nodes in order
        nodes = self.db.query(OutlineNode).filter(
            OutlineNode.run_id == run_id
        ).order_by(OutlineNode.node_id).all()

        # Load drafts
        drafts = self.db.query(Draft).filter(Draft.run_id == run_id).all()
        draft_map = {d.node_id: d for d in drafts}

        # Load documents for bibliography
        documents = self.db.query(Document).all()

        # Build LaTeX
        latex_parts = []

        # Preamble
        latex_parts.append(r"""\documentclass{article}
\usepackage[utf-8]{inputenc}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{hyperref}

\title{""" + run.topic + r"""}
\author{Generated Report}
\date{\today}

\begin{document}
\maketitle
\tableofcontents

""")

        # Sections
        for node in nodes:
            if node.node_id in draft_map:
                level = node.node_id.count(".")
                if level == 0:
                    latex_parts.append(f"\n\\section{{{node.title}}}\n")
                elif level == 1:
                    latex_parts.append(f"\n\\subsection{{{node.title}}}\n")
                else:
                    latex_parts.append(f"\n\\subsubsection{{{node.title}}}\n")

                latex_parts.append(draft_map[node.node_id].latex)
                latex_parts.append("\n")

        # Bibliography
        latex_parts.append(r"""
\begin{thebibliography}{99}
""")

        for doc in documents:
            latex_parts.append(
                f"\\bibitem{{{doc.doc_id}}}\n"
                f"{doc.author or 'Unknown'}. "
                f"{doc.title}. "
                f"{doc.year or 'N/A'}.\n\n"
            )

        latex_parts.append(r"""\end{thebibliography}
\end{document}
""")

        final_latex = "".join(latex_parts)

        return {"latex": final_latex}
