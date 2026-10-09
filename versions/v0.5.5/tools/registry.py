from tools.repository import RepositoryIntelligence
from tools.filesystem import FileSystemTool
from tools.terminal import TerminalTool
from tools.git import GitTool
from tools.search import SearchTool


class ToolRegistry:

    def __init__(self):
        self.filesystem = FileSystemTool()
        self.terminal = TerminalTool()
        self.git = GitTool()
        self.search = SearchTool()

    def list_tools(self):
        return [
            "filesystem",
            "terminal",
            "git",
            "search",
            "repository"
        ]

    def get_tool(self, name):
        tools = {
            "filesystem": self.filesystem,
            "terminal": self.terminal,
            "git": self.git,
            "search": self.search
        }

        if name not in tools:
            raise ValueError(
                f"Tool não encontrada: {name}"
            )

        return tools[name]

    def get_tool_definitions(self):

        return [
            *[{
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": {"type":"object", "properties": props, "required": required}
                }
            } for name, desc, props, required in [
                ("repository_map", "Mapa resumido do repositório selecionado; não lê arquivos sensíveis.", {}, []),
                ("repository_search", "Busca texto nos arquivos de código do projeto selecionado.", {"query":{"type":"string"}}, ["query"]),
                ("repository_symbols", "Encontra definições de classes e funções no projeto selecionado.", {"query":{"type":"string"}}, [])
            ]],
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Lê o conteúdo de um arquivo.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Caminho do arquivo."
                            }
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Cria ou sobrescreve um arquivo de texto UTF-8. Requer confirmação explícita do usuário antes de gravar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Caminho do arquivo."},
                            "content": {"type": "string", "description": "Conteúdo completo a gravar."}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "Lista arquivos e diretórios de um caminho.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Diretório a listar."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": "Procura um texto dentro dos arquivos do projeto.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Texto a procurar."
                            },
                            "path": {
                                "type": "string",
                                "description": "Diretório onde procurar."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Obtém o status atual do Git.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_diff",
                    "description": "Obtém as alterações atuais do Git.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "git_log",
                    "description": "Obtém os últimos commits do Git.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Executa um comando no terminal.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "Comando a executar."
                            }
                        },
                        "required": ["command"]
                    }
                }
            }
        ]

    def set_repository(self, path):
        self.repository = RepositoryIntelligence(path)
        return self.repository.summary()

    def get_repository(self):
        if not hasattr(self, 'repository'):
            self.repository = RepositoryIntelligence('.')
        return self.repository

    def execute(self, name, arguments):
        if name == "repository_map": return self.get_repository().summary()
        if name == "repository_search": return self.get_repository().search(arguments["query"])
        if name == "repository_symbols": return self.get_repository().symbols(arguments.get("query", ""))


        if name == "read_file":
            return self.filesystem.read_file(
                arguments["path"]
            )

        if name == "write_file":
            return self.filesystem.write_file(arguments["path"], arguments["content"])

        if name == "list_files":
            return self.filesystem.list_files(
                arguments.get("path", ".")
            )

        if name == "search_files":
            return self.search.search_files(
                arguments["query"],
                arguments.get("path", ".")
            )

        if name == "git_status":
            return self.git.status()

        if name == "git_diff":
            return self.git.diff()

        if name == "git_log":
            return self.git.log()

        if name == "run_command":
            return self.terminal.run_command(
                arguments["command"]
            )

        raise ValueError(
            f"Tool não encontrada: {name}"
        )