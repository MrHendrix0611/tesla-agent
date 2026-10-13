"""Start with: py -m web.main (Windows) or python -m web.main."""
from web.server import create_app
import uvicorn


def main():
    app = create_app()
    print('Tesla V0.7.0 — Dashboard local')
    print('Abra no navegador: http://127.0.0.1:8765')
    print('Token da extensão VS Code:', app.state.secret)
    print('Não compartilhe este token nem disponibilize a porta 8765 na rede pública.')
    if not app.state.service.agent:
        print('Aviso: nenhum provedor LLM pronto. Configure .env para usar o agente.')
    uvicorn.run(app, host='127.0.0.1', port=8765, log_level='warning')


if __name__ == '__main__':
    main()
