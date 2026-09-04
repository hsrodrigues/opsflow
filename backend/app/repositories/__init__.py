"""Repository layer.

Implemented starting in Fase 2: every repository here will centralize the
`tenant_id` filter for its entity, so that no query issued anywhere in the
application can accidentally skip tenant isolation (seção 3/52/53).
"""
