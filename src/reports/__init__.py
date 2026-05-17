"""Reports module — Q.18.ZIP.BE.4 · completado em Q.22.D-G.

Geração e entrega de relatórios. Endpoints:

  * ``POST /v1/reports/generate``  — gera um relatório on-demand
    (CSV/JSON inline) para download.
  * ``POST /v1/reports/schedule`` / ``GET`` — agendamentos recorrentes
    persistidos em ``reports.report_schedule`` (Q.22.D).
  * ``POST /v1/reports/email``     — gera + entrega por SMTP, persiste
    cada execução em ``reports.report_run`` (Q.22.F).
  * ``POST /v1/reports/retention`` — janela de retenção GDPR + limpeza
    dos runs expirados (Q.22.G).

Templates (closed enum): producao, cliente, qualidade, payroll, cogs,
inventario. Todos delegam aos generators / services live — sem
reimplementar lógica de agregação, sem dados mock.
"""
