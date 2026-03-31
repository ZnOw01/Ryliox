# Guía de Contribución

¡Gracias por tu interés en contribuir a Ryliox!

---

## Configuración del Entorno

### Requisitos

- Python 3.11+
- uv reciente
- Node.js 22.12.0+ o 24.x
- Bun 1.3+

### Instalación

```bash
git clone https://github.com/ZnOw01/Ryliox.git
cd Ryliox
cp .env.example .env
python -m launcher  # Setup automático
```

---

## Estándares de Código

### Python

- **Indentación**: 4 espacios (PEP 8)
- **Máximo línea**: 100 caracteres
- **Type hints** obligatorios para funciones públicas
- **Naming**: `snake_case` funciones/vars, `PascalCase` clases, `UPPER_CASE` constantes

```python
def fetch_book(book_id: str) -> dict:
    """Fetch book metadata.
    
    Args:
        book_id: Unique identifier
        
    Returns:
        Book metadata dict
    """
    return {}
```

### Commits

Formato: `<type>(<scope>): <subject>`

- `feat`: Nueva feature
- `fix`: Bug fix
- `docs`: Documentación
- `refactor`: Refactoring
- `test`: Tests
- `chore`: Mantenimiento

---

## Tests

```bash
# Python
pytest

# Con cobertura
pytest --cov=. --cov-report=html

# Frontend
cd frontend && bun install --frozen-lockfile && bun run check && bun run lint && bun run build
```

---

## Pull Requests

1. Fork y branch: `git checkout -b feature/nombre`
2. Commits descriptivos
3. Tests pasan: `pytest`
4. Push y abre PR en GitHub

---

## Licencia

Al contribuir, aceptas que tu código se licencie bajo GPL v3.
