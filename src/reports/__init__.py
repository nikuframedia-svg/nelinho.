"""Reports module — Q.18.ZIP.BE.4.

Centraliza geração de relatórios on-demand. Por agora um único endpoint
``POST /v1/reports/generate`` que recebe ``template_id`` + ``format``
e devolve dados estruturados (CSV/JSON inline) prontos para download.

Templates suportados delegam aos services existentes (sem reimplementar
lógica de agregação): COGS, Quality, Payroll, Inventory, Forecast.
"""
