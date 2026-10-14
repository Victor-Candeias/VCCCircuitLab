"""Templates de geração automática e layout.

`app.generation.params` define os parâmetros validados de cada template; `app.generation.templates`
implementa os geradores; `app.generation.registry` associa nomes (`series_dc`, `parallel_dc`,
`voltage_divider`, `switch_circuit`) a parâmetros e gerador, para uso pelo endpoint de geração
(E3-02).
"""
