# IMPORTAÇÕES
import socket
import threading
import time
import re
import hashlib
import ssl
import os
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

class HttpBasicInfo:
    def __init__(self):
        self.username = ""
        self.password = ""

# Representa uma sessão de conexão com um dispositivo conectado
class DeviceSession:
    def __init__(self, socket_conn, addr):
        self.socket = socket_conn
        self.addr = addr
        self.token = ""
        self.device_id = ""
        self.connected = True
        self.heartbeat_timer = None
        self.missed_heartbeats = 0

class NetworkManager:
    def __init__(self, log_callback=None):
      
        self.log_callback = log_callback if log_callback else print

      
        self.is_running_register = False
        self.is_running_upload = (
            False
        )

      
        self.device_map = (
            {}
        )
        self.socket_map = {}

      
        self.server_socket = (
            None
        )
        self.http_server = None

      
        self.basic_info = (
            HttpBasicInfo()
        )
        self.heartbeat_interval = 20

      
        self.log_buffer = []
        self.current_log_file = None

    def _get_base_dir(self):
        return os.path.dirname(os.path.abspath(__file__))

    def _save_event_data(self, content):
        try:
            data_dir = os.path.join(self._get_base_dir(), "dados recebidos")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # Tenta parsear como JSON e formatar com indentação
            try:
                json_obj = json.loads(content)
                content_to_save = json.dumps(json_obj, indent=4, ensure_ascii=False)
                extension = ".json"
            except:
                # Se não for JSON válido, salva como texto simples
                content_to_save = content
                extension = ".txt"

            filename = f"evento_{timestamp}{extension}"
            with open(os.path.join(data_dir, filename), "w", encoding="utf-8") as f:
                f.write(content_to_save)
        except Exception as e:
            print(f"Erro ao salvar dados do evento: {e}")

    def _save_json_log(self, content):
        try:
            json_dir = os.path.join(self._get_base_dir(), "json_log")
            if not os.path.exists(json_dir):
                os.makedirs(json_dir)

            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                json_str = content[start : end + 1]

                # Tenta formatar como JSON válido
                try:
                    json_obj = json.loads(json_str)
                    final_content = json.dumps(json_obj, indent=4, ensure_ascii=False)
                    ext = ".json"
                except:
                    # Se falhar, salva como texto simples
                    final_content = json_str
                    ext = ".txt"

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"data_{timestamp}{ext}"
                with open(os.path.join(json_dir, filename), "w", encoding="utf-8") as f:
                    f.write(final_content)
        except Exception as e:
            print(f"Erro ao salvar JSON interno: {e}")

    #   text (string): mensagem para exibir na GUI
    #   file_text (string): mensagem alternativa para salvar em arquivo
    def log(self, text, file_text=None):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

        content_to_write = file_text if file_text is not None else text

        if content_to_write:
            formatted_line = f"{timestamp} {content_to_write}\n"
            if self.current_log_file:
                try:
                    # Adiciona ao final do arquivo de log existente
                    with open(self.current_log_file, "a", encoding="utf-8") as f:
                        f.write(formatted_line)
                except Exception as e:
                    print(f"Erro ao gravar log geral: {e}")
            else:
                # Se arquivo não existe ainda, armazena em buffer
                self.log_buffer.append(formatted_line)

        # Se text está vazio, não faz mais nada
        if not text:
            return

        full_content = content_to_write
        if full_content:
            if "{" in full_content and (
                '"Token"' in full_content
                or '"DeviceID"' in full_content
                or '"DevClass"' in full_content
            ):
                self._save_json_log(full_content)
                return

        # Lista de headers que são "ruidosos" e não agregam informação visual
        hidden_prefixes = [
            "Accept-Encoding",
            "Content-length",
            "Content-Length",
            "Accept-Language",
            "X-XSS-Protection",
            "X-Frame-Options",
            "Content-Security-Policy",
            "Strict-Transport-Security",
            "Referer",
            "Connection",
            "Cache-Control",
            "Pragma",
            "User-Agent",
            "Host",
        ]

        # Remove linhas em branco e headers desnecessários
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            # Pula linhas em branco
            if not line.strip():
                continue
            # Pula headers na lista de exclusão
            if any(line.strip().startswith(prefix) for prefix in hidden_prefixes):
                continue
            clean_lines.append(line)

        # Exibe na GUI apenas as linhas relevantes
        gui_text = "\n".join(clean_lines)
        if gui_text.strip():
            self.log_callback(gui_text)

    def _init_log_file(self, device_id):
        # Se já existe arquivo de log aberto, não abre outro
        if self.current_log_file:
            return

        try:
            log_dir = os.path.join(self._get_base_dir(), "log")
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            timestamp_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{device_id}_{timestamp_filename}.txt"
            self.current_log_file = os.path.join(log_dir, filename)

            with open(self.current_log_file, "w", encoding="utf-8") as f:
                f.write(f"--- SESSÃO INICIADA: {device_id} ---\n")
                # Despeja buffer de logs coletados antes da inicialização
                for line in self.log_buffer:
                    f.write(line)

            self.log_buffer = []
            self.log_callback(f"Arquivo de log criado: {filename}")
        except Exception as e:
            self.log_callback(f"Erro ao criar arquivo de log: {e}")

    # Calcula hash MD5 de uma string (usado em autenticação HTTP Digest)
    def calculate_md5(self, input_str):
        return hashlib.md5(input_str.encode("utf-8")).hexdigest().lower()

    #   text (string): texto para buscar
    #   pattern (string): padrão regex com grupo de captura
    def _extract_regex(self, text, pattern):
        match = re.search(pattern, text)
        return match.group(1) if match else ""

    #   username, password: credenciais do usuário
    #   realm: domínio da autenticação
    #   method: método HTTP (POST, GET, etc.)
    #   uri: URI do recurso solicitado
    #   nonce: valor único fornecido pelo servidor
    #   nc: número de contagem (00000001)
    #   cnonce: nonce do cliente
    #   qop: qualidade de proteção (auth)
    def generate_auth_response(
        self, username, password, realm, method, uri, nonce, nc, cnonce, qop
    ):
        # Calcula HA1 = MD5(username:realm:password)
        ha1 = self.calculate_md5(f"{username}:{realm}:{password}")
        # Calcula HA2 = MD5(method:uri)
        ha2 = self.calculate_md5(f"{method}:{uri}")
        # Calcula resposta final = MD5(HA1:nonce:nc:cnonce:qop:HA2)
        response = self.calculate_md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
        return response

    #   ip (string): endereço IP para bind do servidor
    #   port (int/string): porta do servidor
    #   username, password (string): credenciais de autenticação
    #   heartbeat_interval (int): segundos entre keep-alives
    #   use_ssl (bool): habilitar SSL/TLS?
    #   cert_file, key_file (string): caminhos para certificado e chave
    def start_listen_auto_register(
        self,
        ip,
        port,
        username,
        password,
        heartbeat_interval=20,
        use_ssl=False,
        cert_file="",
        key_file="",
    ):
        # Evita iniciar múltiplas instâncias do servidor
        if self.is_running_register:
            return False

        # Reseta estado (logs e buffer) para nova sessão
        self.current_log_file = None
        self.log_buffer = []
        self.basic_info.username = username
        self.basic_info.password = password

        try:
            self.heartbeat_interval = int(heartbeat_interval)
            if self.heartbeat_interval < 1:
                self.heartbeat_interval = 20
        except ValueError:
            self.heartbeat_interval = 20

        try:
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            raw_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            raw_socket.bind((ip, int(port)))
            raw_socket.listen(5)

            if use_ssl:
                try:
                    base_dir = self._get_base_dir()
                    cert_path = os.path.join(base_dir, cert_file)
                    key_path = os.path.join(base_dir, key_file)
                    if not os.path.exists(cert_path):
                        raise FileNotFoundError(
                            f"Certificado não encontrado: {cert_path}"
                        )
                    if not os.path.exists(key_path):
                        raise FileNotFoundError(f"Chave não encontrada: {key_path}")
                    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
                    self.server_socket = context.wrap_socket(
                        raw_socket, server_side=True
                    )
                    self.log(
                        f"Backend: Servidor HTTPS (SSL) iniciado em {ip}:{port} (Heartbeat: {self.heartbeat_interval}s)"
                    )
                except Exception as ssl_err:
                    self.log(f"Erro SSL Crítico: {ssl_err}")
                    raw_socket.close()
                    return False
            else:
                # Sem SSL, usa socket TCP direto
                self.server_socket = raw_socket
                self.log(
                    f"Backend: Servidor TCP (HTTP) iniciado em {ip}:{port} (Heartbeat: {self.heartbeat_interval}s)"
                )

            self.is_running_register = True
            threading.Thread(target=self._listen_connect_socket, daemon=True).start()
            return True

        except Exception as e:
            self.log(f"Backend Erro: {e}")
            return False

    def stop_listen_auto_register(self):
        self.is_running_register = False
        self.current_log_file = None

        # Fecha o socket do servidor (interrompe accept)
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        for sock, session in list(self.socket_map.items()):
            try:
                session.connected = False
                if session.heartbeat_timer:
                    session.heartbeat_timer.cancel()
                sock.close()
            except:
                pass

        self.device_map.clear()
        self.socket_map.clear()
        self.log("Backend: Servidor TCP parado.")

    # Loop principal que aceita novas conexões de dispositivos
    def _listen_connect_socket(self):
        while self.is_running_register:
            try:
                client_sock, addr = self.server_socket.accept()

                session = DeviceSession(client_sock, addr)
                self.socket_map[client_sock] = session

                threading.Thread(
                    target=self._handle_client_response, args=(session,), daemon=True
                ).start()
            except OSError:
                # Erro normal quando servidor foi fechado
                break
            except Exception as e:
                self.log(f"Accept error: {e}")

    # Loop que recebe e processa mensagens de um dispositivo
    # Lida com autenticação e preparação do dispositivo
    def _handle_client_response(self, session):
        client = session.socket
        addr = session.addr

        # Loop de recepção de dados enquanto servidor está ativo e dispositivo conectado
        while self.is_running_register and session.connected:
            try:
                recv_buffer = client.recv(2048 * 1024)
                if not recv_buffer:
                    # Socket fechado pelo cliente de forma limpa
                    break

                # Decodifica a mensagem recebida
                msg = recv_buffer.decode("utf-8", errors="ignore")

                # Se recebeu resposta "200 OK" ao heartbeat ou qualquer outra mensagem
                if "200 OK" in msg:
                    self.log(f"Resposta de Heartbeat recebida de {addr}")
                    session.missed_heartbeats = 0
                elif msg.strip():
                    session.missed_heartbeats = 0

                remote_ip = addr[0]
                self.log(
                    f"Recebido de {addr}:\n{msg[:200]}...",
                    file_text=f"Recebido de {addr}:\n{msg}",
                )

                if "/cgi-bin/api/autoRegist/connect" in msg:
                    match = re.search(r'"DeviceID"\s*:\s*"([0-9a-zA-Z]+)"', msg)
                    if match:
                        dev_id = match.group(1)
                        session.device_id = dev_id
                        self.device_map[session.device_id] = session
                        self._init_log_file(dev_id)
                        self.log(f"Dispositivo Conectado: {session.device_id}")

                    client.send(
                        b"HTTP/1.1 200 OK\r\nConnection: keep-alive\r\nContent-Length: 0\r\n\r\n"
                    )
                    time.sleep(0.5)
                    client.send(
                        f"POST /cgi-bin/api/global/login HTTP/1.1\r\nHost: {remote_ip}\r\nContent-Length: 0\r\n\r\n".encode()
                    )

                elif "HTTP/1.1 401 Unauthorized" in msg:
                    nonce = self._extract_regex(msg, r'nonce="([^"]+)"')
                    realm = self._extract_regex(msg, r'realm="([^"]+)"')
                    qop = self._extract_regex(msg, r'qop="([^"]+)"')
                    uri = "/cgi-bin/api/global/login"
                    cnonce = "004fd20e9f803827de4c39fa3a9fb115"

                    resp_hash = self.generate_auth_response(
                        self.basic_info.username,
                        self.basic_info.password,
                        realm,
                        "POST",
                        uri,
                        nonce,
                        "00000001",
                        cnonce,
                        qop,
                    )

                    # Monta header de autenticação
                    opaque = self._extract_regex(msg, r'opaque="([^"]+)"')
                    auth_header = f'Authorization: Digest username="{self.basic_info.username}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{resp_hash}", opaque="{opaque}", qop={qop}, nc=00000001, cnonce="{cnonce}"'
                    full_req = f"POST {uri} HTTP/1.1\r\n{auth_header}\r\nHost: {remote_ip}\r\nContent-Length: 0\r\n\r\n"

                    client.send(full_req.encode())
                    self.log("", file_text=f"Enviado para {addr}:\n{full_req}")

                elif '"Token"' in msg:
                    token = self._extract_regex(msg, r'"Token"\s*:\s*"([0-9a-zA-Z]+)"')
                    session.token = token
                    self.log(f"Login OK! Token: {token}")
                    self._start_heartbeat(session)

            except Exception as e:
                # Não mata o servidor, deixa o heartbeat tentar enviar 3 vezes
                self.log(
                    "",
                    file_text=f"Erro de leitura no socket (esperado se desconectado): {e}",
                )
                session.connected = False
                break

        # Não limpamos maps aqui para permitir que o heartbeat tente enviar e falhe 3 vezes

    def _start_heartbeat(self, session):
        def hb():
            # Loop que executa enquanto o servidor está ativo
            while self.is_running_register:
                time.sleep(self.heartbeat_interval)

                # Se o servidor parou durante o sleep, sai
                if not self.is_running_register:
                    break

                if session.missed_heartbeats >= 3:
                    self.log(
                        "O dispositivo perdeu conexão com servidor (3 falhas de heartbeat)"
                    )
                    session.connected = False
                    try:
                        session.socket.close()
                    except:
                        pass
                    break

                session.missed_heartbeats += 1

                try:
                    # Monta requisição HTTP POST com token de autenticação
                    req = f"POST /cgi-bin/api/global/keep-alive HTTP/1.1\r\nHost: {session.addr[0]}\r\nX-cgi-token: {session.token}\r\nContent-Length: 0\r\n\r\n"
                    session.socket.send(req.encode())

                    # Se enviou com sucesso, registra na GUI
                    self.log(
                        f"Heartbeat enviado para {session.addr[0]} (Tentativa: {session.missed_heartbeats}/3)"
                    )
                    self.log("", file_text=f"Enviado Heartbeat:\n{req}")

                except Exception as e:
                    # Se falhar, apenas registra o erro
                    # Não encerra a thread - deixa tentar novamente na próxima iteração
                    self.log(
                        f"Falha ao enviar Heartbeat para {session.addr[0]} (Tentativa: {session.missed_heartbeats}/3). Erro de Socket."
                    )
                    # Loop continua, vai dormir e tentar de novo até dar 3 strikes

        t = threading.Thread(target=hb, daemon=True)
        session.heartbeat_timer = t
        t.start()

    #   device_id (string): ID do dispositivo alvo
    #   method (string): método HTTP (GET, POST, etc.)
    #   uri (string): caminho da requisição
    #   data (string): corpo da requisição (optional)
    def send_request(self, device_id, method, uri, data):
        if device_id not in self.device_map:
            self.log("Erro: Device ID não encontrado.")
            return False

        session = self.device_map[device_id]
        try:
            clean_data = data.replace("\n", "\r\n") if data else ""

            # Monta requisição HTTP com token de autenticação
            req = f"{method} {uri} HTTP/1.1\r\nHost: {session.addr[0]}\r\nX-cgi-token: {session.token}\r\nConnection: keep-alive\r\nContent-Length: {len(clean_data)}\r\n\r\n{clean_data}"

            session.socket.send(req.encode())
            self.log(f"Request enviado para {device_id}")
            self.log("", file_text=f"Enviado Manualmente para {device_id}:\n{req}")
            return True
        except Exception as e:
            self.log(f"Erro Request: {e}")
            return False

    def is_device_login(self, device_id):
        return device_id in self.device_map

    #   prefix_url (string): URL para extrair porta (ex: "http://localhost:8080")
    #   use_ssl (bool): habilitar SSL/TLS?
    #   cert_file, key_file (string): caminhos para certificado e chave
    def start_listen_upload(self, prefix_url, use_ssl=False, cert_file="", key_file=""):
        match = re.search(r":(\d+)", prefix_url)
        port = int(match.group(1)) if match else 80

        # Evita iniciar múltiplas instâncias
        if self.is_running_upload:
            return

        # Referência para acessar self dentro da classe interna RequestHandler
        manager_ref = self

        # Manipula requisições HTTP POST e GET de eventos
        class RequestHandler(BaseHTTPRequestHandler):
            # Suprime logs padrão do servidor HTTP
            def log_message(self, format, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8", errors="ignore")

                manager_ref._save_event_data(body)

                # Tenta validar como JSON
                try:
                    json.loads(body)
                    manager_ref.log(
                        "Dados Post Evento 2.0 recebido com sucesso!",
                        file_text=f"POST Recebido (JSON):\n{body}",
                    )
                except:
                    # Se não for JSON, trata como texto simples
                    manager_ref.log(
                        "Dados Post Evento recebido com sucesso!",
                        file_text=f"POST Recebido (TXT):\n{body}",
                    )

                self.send_response(200)
                self.send_header("Content-type", "application/json;charset=UTF-8")
                self.end_headers()

            def do_GET(self):
                self.send_response(200)
                self.end_headers()

        try:
            self.http_server = HTTPServer(("0.0.0.0", port), RequestHandler)

            # Aplica SSL/TLS se solicitado
            if use_ssl:
                try:
                    base_dir = manager_ref._get_base_dir()
                    cert_path = os.path.join(base_dir, cert_file)
                    key_path = os.path.join(base_dir, key_file)
                    if not os.path.exists(cert_path):
                        raise FileNotFoundError(
                            f"Certificado não encontrado: {cert_path}"
                        )
                    if not os.path.exists(key_path):
                        raise FileNotFoundError(f"Chave não encontrada: {key_path}")
                    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
                    self.http_server.socket = context.wrap_socket(
                        self.http_server.socket, server_side=True
                    )
                    self.log(f"Backend: Post Eventos (HTTPS) iniciado na porta {port}")
                except Exception as ssl_err:
                    self.log(f"Erro SSL no Listener: {ssl_err}")
                    return False
            else:
                self.log(f"Backend: Post Eventos (HTTP) iniciado na porta {port}")

            self.is_running_upload = True
            threading.Thread(target=self.http_server.serve_forever, daemon=True).start()
            return True
        except Exception as e:
            self.log(f"Erro HTTP Server: {e}")
            return False

    def stop_listen_upload(self):
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()

        self.is_running_upload = False
        self.log("Backend: Post Eventos parado.")
