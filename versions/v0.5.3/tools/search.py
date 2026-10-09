from pathlib import Path


class SearchTool:

    def search_files(
        self,
        query: str,
        path: str = "."
    ) -> list[str]:

        root = Path(path)

        if not root.exists():
            raise FileNotFoundError(
                f"Caminho não encontrado: {path}"
            )

        results = []

        for file_path in root.rglob("*"):

            if not file_path.is_file():
                continue

            try:

                content = file_path.read_text(
                    encoding="utf-8"
                )

                if query.lower() in content.lower():
                    results.append(
                        str(file_path)
                    )

            except (UnicodeDecodeError, PermissionError):
                continue

        return results