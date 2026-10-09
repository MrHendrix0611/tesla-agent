import json

from core.context import ContextManager
from core.skill_manager import SkillManager
from llm.router import LLMRouter
from tools.registry import ToolRegistry
from core.permission_manager import PermissionManager

class Agent:

    def __init__(self):

        self.llm = LLMRouter()
        self.context = ContextManager()
        self.skills = SkillManager()
        self.tools = ToolRegistry()
        self.permissions = PermissionManager()
        self.max_tool_calls = 3

        self.active_skill = None

        self.system_prompt = """
            Você é Tesla, um agente de inteligência artificial
            especializado em ajudar o usuário.

            Responda de forma clara, objetiva e útil.

            Você possui acesso a ferramentas que podem ser utilizadas
            quando forem necessárias para responder ao usuário.

            Ao trabalhar com código, use repository_map para conhecer o projeto,
            repository_symbols para localizar definições e repository_search para encontrar trechos.
            Nunca invente arquivos nem presuma que o mapa contém todos os arquivos.

            REGRAS DE USO DAS FERRAMENTAS:

            1. Use uma ferramenta somente quando ela for necessária.

            2. Depois que uma ferramenta fornecer informação suficiente
            para responder à solicitação do usuário, pare de utilizar
            ferramentas e responda ao usuário.

            3. Não execute ferramentas repetidamente para obter a mesma
            informação.

            4. Não tente várias alternativas de comando para descobrir
            uma informação que já foi obtida.

            5. Nunca invente resultados de ferramentas.

            6. Se uma ferramenta retornar um resultado válido, utilize
            esse resultado para construir a resposta final.

            7. Ferramentas que exigem confirmação devem aguardar a
            autorização do usuário.

            8. Para criar ou corrigir arquivos de texto, use write_file,
            informando caminho e conteúdo completo. Essa ferramenta
            sobrescreve o arquivo e exige confirmação do usuário.
            """

    def set_skill(self, skill_name):

        if not self.skills.skill_exists(skill_name):
            raise ValueError(
                f"Skill não encontrada: {skill_name}"
            )

        self.active_skill = skill_name

    def clear_skill(self):
        self.active_skill = None

    def get_active_skill(self):
        return self.active_skill

    def run(self, user_input: str) -> str:

        self.context.add_user_message(user_input)

        system_prompt = self.system_prompt

        if self.active_skill:

            skill_instructions = self.skills.load_skill(
                self.active_skill
            )

            system_prompt += f"""

    Você está utilizando a seguinte Skill:

    {skill_instructions}
    """

        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        messages.extend(
            self.context.get_messages()
        )

        tools = self.tools.get_tool_definitions()

        tool_calls_count = 0
        max_iterations = 5

        for _ in range(max_iterations):

            response = self.llm.generate(
                messages,
                tools=tools
            )

            tool_calls = response.get(
                "tool_calls",
                []
            )

            if not tool_calls:

                final_response = response.get(
                    "content",
                    ""
                )

                self.context.add_assistant_message(
                    final_response
                )

                return final_response

            if tool_calls_count + len(tool_calls) > self.max_tool_calls:

                final_response = (
                    "Interrompi a execução porque o limite de "
                    "ferramentas para esta solicitação foi atingido."
                )

                self.context.add_assistant_message(
                    final_response
                )

                return final_response

            assistant_message = {
                "role": "assistant",
                "content": response.get(
                    "content",
                    ""
                ),
                "tool_calls": []
            }

            for tool_call in tool_calls:

                assistant_message["tool_calls"].append({
                    "id": tool_call["id"],
                    "type": "function",
                    "function": {
                        "name": tool_call["name"],
                        "arguments": tool_call["arguments"]
                    }
                })

            messages.append(
                assistant_message
            )

            for tool_call in tool_calls:

                tool_calls_count += 1

                tool_name = tool_call["name"]

                try:

                    arguments = json.loads(
                        tool_call["arguments"]
                    )

                    permission = self.permissions.get_status(
                        tool_name
                    )

                    if permission == "allowed":

                        result = self.tools.execute(
                            tool_name,
                            arguments
                        )

                    elif permission == "confirmation_required":

                        confirmed = self.confirm_tool(
                            tool_name,
                            arguments
                        )

                        if confirmed:

                            result = self.tools.execute(
                                tool_name,
                                arguments
                            )

                        else:

                            result = (
                                "O usuário não autorizou "
                                f"a execução da Tool '{tool_name}'."
                            )

                    else:

                        result = (
                            f"A Tool '{tool_name}' não possui "
                            "permissão para ser executada."
                        )

                except Exception as error:

                    result = (
                        f"Erro ao executar Tool: {error}"
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result)
                })

        error_message = (
            "Interrompi a execução porque o limite de "
            "iterações do agente foi atingido."
        )

        self.context.add_assistant_message(
            error_message
        )

        return error_message

    def confirm_tool(self, tool_name: str, arguments: dict) -> bool:
        print()
        print("⚠️ Ação requer confirmação.")
        print(f"Tool: {tool_name}")
        print(f"Argumentos: {arguments}")

        answer = input("Deseja permitir? [s/N]: ")

        return answer.lower() in ["s", "sim", "y", "yes"]