import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from app.config import Config

class GitServiceError(Exception):
    """Exceção customizada para erros em operações do Git."""
    def __init__(self, message: str, stdout: str = "", stderr: str = "", returncode: int = 1):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def run_git_command(args: List[str], cwd: Optional[Path] = None, timeout: int = 30) -> Tuple[int, str, str]:
    """
    Executa um comando git no diretório do repositório com tratamento robusto
    de encoding utf-8 e captura de stdout e stderr.
    """
    target_cwd = cwd or Config.REPO_PATH
    if not target_cwd or not target_cwd.exists():
        raise GitServiceError(f"Diretório do repositório não encontrado: {target_cwd}")
        
    cmd = ["git"] + args
    try:
        process = subprocess.run(
            cmd,
            cwd=str(target_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False
        )
        return process.returncode, process.stdout.strip(), process.stderr.strip()
    except subprocess.TimeoutExpired:
        raise GitServiceError(f"Tempo limite de {timeout}s expirado para o comando: {' '.join(cmd)}")
    except FileNotFoundError:
        raise GitServiceError("Executável do 'git' não encontrado no PATH do sistema operacional.")
    except Exception as e:
        raise GitServiceError(f"Erro inesperado ao executar git: {str(e)}")


def get_repo_status() -> Dict[str, Any]:
    """
    Coleta informações detalhadas sobre o estado atual do repositório Git:
    - Se é um repositório git válido
    - Branch atual
    - URL do remote origin
    - Último commit
    - Status de arquivos modificados / limpo
    """
    repo_path = Config.REPO_PATH
    info: Dict[str, Any] = {
        "is_git_repo": False,
        "repo_path": str(repo_path),
        "branch": "",
        "remote_url": "",
        "latest_commit_hash": "",
        "latest_commit_message": "",
        "latest_commit_date": "",
        "is_clean": True,
        "uncommitted_files": [],
        "error": None
    }
    
    if not repo_path or not repo_path.exists():
        info["error"] = f"Caminho do repositório não existe: {repo_path}"
        return info
        
    # Verifica se é repositório Git
    code, out, err = run_git_command(["rev-parse", "--is-inside-work-tree"])
    if code != 0 or out != "true":
        info["error"] = f"A pasta '{repo_path}' não é um repositório Git válido."
        return info
        
    info["is_git_repo"] = True
    
    # Branch atual
    _, branch, _ = run_git_command(["branch", "--show-current"])
    info["branch"] = branch or "main"
    
    # Remote URL
    _, remote_url, _ = run_git_command(["remote", "get-url", Config.GIT_REMOTE])
    info["remote_url"] = remote_url
    
    # Último commit
    code, log_out, _ = run_git_command(["log", "-1", "--format=%h||%s||%cd", "--date=format:%d/%m/%Y %H:%M"])
    if code == 0 and "||" in log_out:
        parts = log_out.split("||")
        info["latest_commit_hash"] = parts[0]
        info["latest_commit_message"] = parts[1]
        info["latest_commit_date"] = parts[2] if len(parts) > 2 else ""
        
    # Status de alterações
    code, status_out, _ = run_git_command(["status", "--porcelain"])
    if code == 0:
        lines = [line.strip() for line in status_out.split("\n") if line.strip()]
        info["is_clean"] = len(lines) == 0
        info["uncommitted_files"] = lines

    # Verifica se há commits pendentes de push (ahead of remote)
    code, ahead_out, _ = run_git_command(["rev-list", f"{Config.GIT_REMOTE}/{info['branch']}..HEAD", "--count"])
    try:
        info["ahead_count"] = int(ahead_out) if code == 0 else 0
    except (ValueError, TypeError):
        info["ahead_count"] = 0
        
    return info


def git_pull(branch: Optional[str] = None, remote: Optional[str] = None) -> Tuple[bool, str]:
    """
    Executa 'git pull origin main' para sincronizar com o repositório remoto.
    """
    target_branch = branch or Config.GIT_BRANCH
    target_remote = remote or Config.GIT_REMOTE
    
    code, stdout, stderr = run_git_command(["pull", target_remote, target_branch])
    output = stdout or stderr
    if code != 0:
        raise GitServiceError(
            f"Falha ao executar 'git pull {target_remote} {target_branch}': {stderr or stdout}",
            stdout=stdout,
            stderr=stderr,
            returncode=code
        )
    return True, output


def git_add(file_paths: List[str]) -> Tuple[bool, str]:
    """Executa 'git add' para os arquivos especificados."""
    if not file_paths:
        return True, "Nenhum arquivo para adicionar."
        
    args = ["add"] + file_paths
    code, stdout, stderr = run_git_command(args)
    if code != 0:
        raise GitServiceError(
            f"Falha ao executar 'git add': {stderr or stdout}",
            stdout=stdout,
            stderr=stderr,
            returncode=code
        )
    return True, stdout


def git_commit(message: str) -> Tuple[bool, str, str]:
    """
    Executa 'git commit -m <message>'.
    Retorna (sucesso, commit_hash, output).
    """
    code, stdout, stderr = run_git_command(["commit", "-m", message])
    if code != 0:
        raise GitServiceError(
            f"Falha ao criar commit: {stderr or stdout}",
            stdout=stdout,
            stderr=stderr,
            returncode=code
        )
        
    # Obtém o hash do commit recém criado
    _, hash_out, _ = run_git_command(["rev-parse", "--short", "HEAD"])
    return True, hash_out, stdout


def git_push(branch: Optional[str] = None, remote: Optional[str] = None, max_retries: int = 3, retry_delay: float = 2.0) -> Tuple[bool, str]:
    """
    Executa 'git push origin main' com mecanismo resiliente de retry automático
    para tratar oscilações transitórias de rede e erros HTTP 500 do GitHub (Internal Server Error).
    """
    target_branch = branch or Config.GIT_BRANCH
    target_remote = remote or Config.GIT_REMOTE
    
    last_error = ""
    for attempt in range(1, max_retries + 1):
        # Aumenta buffer de upload para evitar timeout em imagens
        code, stdout, stderr = run_git_command(
            ["-c", "http.postBuffer=524288000", "push", target_remote, target_branch],
            timeout=60
        )
        if code == 0:
            return True, stdout or stderr
            
        combined_err = f"{stderr} {stdout}".strip()
        last_error = combined_err
        
        # Verifica se é erro transitório que merece retry
        is_transient = any(msg in combined_err for msg in [
            "Internal Server Error",
            "HTTP 500",
            "502",
            "503",
            "504",
            "Connection reset",
            "Could not resolve host",
            "Failed to connect",
            "The remote end hung up unexpectedly"
        ])
        
        if is_transient and attempt < max_retries:
            time.sleep(retry_delay * attempt)
            continue
        elif not is_transient:
            break

    raise GitServiceError(
        f"Falha ao executar 'git push {target_remote} {target_branch}': {last_error}",
        stderr=last_error,
        returncode=1
    )

