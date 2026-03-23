# IMPORTAÇÕES
import customtkinter as ctk
from datetime import datetime
import re
import json
import os
import socket

# Aplicação principal com interface gráfica em customtkinter
# Responsável por: UI, controle de servidor TCP/HTTP, envio de requisições
class MainApp(ctk.CTk):
    def __init__(self, network_manager_class):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("CGI Autocgi")
        self.geometry("1150x800")
        self.minsize(900, 650)

        # Localiza o diretório do script para carregar/salvar config.json
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(base_dir, "config.json")

        # Carrega histórico de configurações do arquivo JSON
        self.history = self.load_config()

        # Instancia o gerenciador de rede com callback para exibir logs
        self.backend = network_manager_class(log_callback=self.log_to_ui)

        # Configura grid para layout responsivo
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.fonts = {
            "header": ("Roboto Medium", 16),
            "sub_header": ("Roboto Medium", 13),
            "body": ("Roboto", 12),
            "mono": ("Consolas", 12),
        }

        self._create_sidebar()
        self._create_main_content()

        self.check_login_status()

    # Carrega configurações do arquivo JSON ou define padrões
    def load_config(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            detected_ip = s.getsockname()[0]
            s.close()
        except:
            # Fallback se falhar detecção
            detected_ip = "127.0.0.1"

        default_data = {
            "ips": [detected_ip],
            "ports": ["60002"],
            "prefixes": [
                f"http://{detected_ip}:60003/"
            ],
            "device_ids": ["1"],
        }

        if os.path.exists(self.config_file):
            try:
                # Tenta carregar arquivo JSON existente
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Mescla com valores padrão se algum estiver faltando
                    for key in default_data:
                        if key not in data:
                            data[key] = default_data[key]
                    return data
            except:
                # Se houver erro ao carregar, retorna padrão
                return default_data
        return default_data

    def save_history(self, key, value):
        # Remove espaços em branco
        value = value.strip()
        if not value:
            return

        current_list = self.history[key]
        if value in current_list:
            # Remove se já existe
            current_list.remove(value)
        # Insere no início da lista
        current_list.insert(0, value)
        # Mantém apenas os 10 mais recentes
        self.history[key] = current_list[:10]

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")

        if key == "ips":
            self.entry_ip.configure(values=self.history["ips"])
            self.entry_ip.set(value)
        elif key == "ports":
            self.entry_port.configure(values=self.history["ports"])
            self.entry_port.set(value)
        elif key == "prefixes":
            self.entry_prefix.configure(values=self.history["prefixes"])
            self.entry_prefix.set(value)
        elif key == "device_ids":
            self.entry_dev_id.configure(values=self.history["device_ids"])
            self.entry_dev_id.set(value)

    # Contém: autenticação, configurações TCP, e controle de POST eventos
    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(
            10, weight=1
        )

        lbl_logo = ctk.CTkLabel(
            self.sidebar, text="AUTOCGI 2.0", font=("Roboto", 24, "bold")
        )
        lbl_logo.grid(row=0, column=0, padx=20, pady=(30, 20))

        self._create_separator(self.sidebar, "AUTENTICAÇÃO", 1)
        self.entry_user = self._create_labeled_entry(
            self.sidebar, "Usuário:", "admin", 2
        )

        # Label e entrada para senha
        lbl_pass = ctk.CTkLabel(self.sidebar, text="Senha:", font=self.fonts["body"])
        lbl_pass.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")

        # Frame para senha com checkbox de visibilidade
        pass_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        pass_frame.grid(row=4, column=0, padx=20, pady=(0, 5), sticky="ew")

        self.entry_pass = ctk.CTkEntry(pass_frame, show="*")
        self.entry_pass.pack(side="top", fill="x", expand=True)
        self.entry_pass.insert(0, "acesso1234")

        self.chk_show_pass = ctk.CTkCheckBox(
            pass_frame,
            text="Mostrar senha",
            font=("Roboto", 11),
            checkbox_width=18,
            checkbox_height=18,
            command=self.toggle_password_visibility,
        )
        self.chk_show_pass.pack(side="top", anchor="w", pady=(5, 0))

        self._create_separator(self.sidebar, "SERVIDOR LOCAL (TCP)", 5)

        # Frame horizontal para IP e Porta lado a lado
        tcp_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        tcp_frame.grid(row=6, column=0, padx=20, sticky="ew")

        # ComboBox para IP (com histórico)
        ip_col = ctk.CTkFrame(tcp_frame, fg_color="transparent")
        ip_col.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(
            ip_col, text="IP Local:", font=self.fonts["body"], anchor="w"
        ).pack(fill="x")
        self.entry_ip = ctk.CTkComboBox(ip_col, values=self.history["ips"])
        self.entry_ip.pack(fill="x")
        if self.history["ips"]:
            self.entry_ip.set(self.history["ips"][0])

        # ComboBox para Porta (com histórico)
        port_col = ctk.CTkFrame(tcp_frame, fg_color="transparent")
        port_col.pack(side="right")
        ctk.CTkLabel(port_col, text="Porta:", font=self.fonts["body"], anchor="w").pack(
            fill="x"
        )
        self.entry_port = ctk.CTkComboBox(
            port_col, width=90, values=self.history["ports"]
        )
        self.entry_port.pack(fill="x")
        if self.history["ports"]:
            self.entry_port.set(self.history["ports"][0])

        # Entrada para intervalo de heartbeat
        self.entry_hb = self._create_labeled_entry(
            self.sidebar, "Heartbeat (segundos):", "20", 7
        )

        # Switch para habilitar SSL/TLS
        self.chk_ssl = ctk.CTkSwitch(
            self.sidebar, text="Habilitar HTTPS (SSL)", font=self.fonts["body"]
        )
        self.chk_ssl.grid(row=8, column=0, padx=20, pady=15, sticky="w")

        # Botão para iniciar/parar servidor TCP
        self.btn_register = ctk.CTkButton(
            self.sidebar,
            text="INICIAR SERVIDOR",
            height=40,
            font=("Roboto", 13, "bold"),
            command=self.toggle_register,
        )
        self.btn_register.grid(row=9, column=0, padx=20, pady=10, sticky="ew")

        self._create_separator(self.sidebar, "POST EVENTOS", 10)

        # ComboBox para URL/Prefix do servidor HTTP
        http_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        http_frame.grid(row=11, column=0, padx=20, pady=(0, 5), sticky="ew")
        self.entry_prefix = ctk.CTkComboBox(http_frame, values=self.history["prefixes"])
        self.entry_prefix.pack(fill="x")
        if self.history["prefixes"]:
            self.entry_prefix.set(self.history["prefixes"][0])

        # Switch para SSL/TLS na upload de eventos
        self.chk_ssl_upload = ctk.CTkSwitch(
            self.sidebar, text="Habilitar HTTPS (SSL)", font=self.fonts["body"]
        )
        self.chk_ssl_upload.grid(row=12, column=0, padx=20, pady=(10, 10), sticky="w")

        # Botão para ativar/parar servidor HTTP
        self.btn_upload = ctk.CTkButton(
            self.sidebar,
            text="Ativar Post Eventos",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "#DCE4EE"),
            command=self.toggle_upload,
        )
        self.btn_upload.grid(row=13, column=0, padx=20, pady=(0, 20), sticky="ew")

    def _create_main_content(self):
        """Área direita expansível"""
        main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        main_frame.grid_rowconfigure(1, weight=3)
        main_frame.grid_rowconfigure(3, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(
            main_frame, fg_color=("gray85", "gray17"), corner_radius=8
        )
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ctk.CTkLabel(
            top_bar, text="Dispositivo Alvo (ID):", font=self.fonts["sub_header"]
        ).pack(side="left", padx=15, pady=12)
        self.entry_dev_id = ctk.CTkComboBox(
            top_bar,
            width=220,
            font=self.fonts["mono"],
            values=self.history["device_ids"],
        )
        self.entry_dev_id.pack(side="left", pady=12)
        if self.history["device_ids"]:
            self.entry_dev_id.set(self.history["device_ids"][0])

        self.lbl_status = ctk.CTkLabel(
            top_bar,
            text="● Desconectado",
            text_color="gray",
            font=("Roboto", 13, "bold"),
        )
        self.lbl_status.pack(side="right", padx=20)

        req_card = ctk.CTkFrame(main_frame)
        req_card.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        req_card.grid_columnconfigure(1, weight=1)
        req_card.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(req_card, text="Método:", font=self.fonts["body"]).grid(
            row=0, column=0, padx=15, pady=15, sticky="w"
        )
        self.entry_method = ctk.CTkComboBox(
            req_card, values=["POST", "GET", "PUT", "DELETE"], width=110
        )
        self.entry_method.grid(row=0, column=0, padx=(70, 0), pady=15, sticky="w")
        self.entry_method.set("POST")

        self.entry_url = ctk.CTkEntry(req_card, placeholder_text="/url...")
        self.entry_url.grid(row=0, column=1, padx=15, pady=15, sticky="ew")
        self.entry_url.insert(0, "/cgi-bin/AccessUser.cgi?action=insertMulti")

        ctk.CTkLabel(req_card, text="Payload (JSON):", font=self.fonts["body"]).grid(
            row=1, column=0, padx=15, pady=0, sticky="nw"
        )

        self.text_json = ctk.CTkTextbox(
            req_card,
            height=280,
            font=self.fonts["mono"],
            fg_color=("gray95", "#1a1a1a"),
        )
        self.text_json.grid(
            row=2, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="nsew"
        )

        default_json = """{
    "UserList": [
        {
            "UserID": "1", 
            "UserName": "test1", 
            "UserType": 0, 
            "UseTime": 200, 
            "IsFirstEnter": false,
            "FirstEnterDoors": [0, 1], 
            "UserStatus": 0, 
            "Authority": 1, 
            "CitizenIDNo": "123456789012345678",
            "Password": "234", 
            "Doors": [0], 
            "TimeSections": [255], 
            "SpecialDaysSchedule": [255],
            "ValidFrom": "2019-01-02 00:00:00", 
            "ValidTo": "2037-01-02 01:00:00"
        },
        {
            "UserID": "2", 
            "UserName": "test2", 
            "UserType": 0, 
            "UseTime": 200, 
            "IsFirstEnter": false,
            "FirstEnterDoors": [0, 1], 
            "UserStatus": 0, 
            "Authority": 2, 
            "CitizenIDNo": "123456789012345678",
            "Password": "234", 
            "Doors": [0], 
            "TimeSections": [255], 
            "SpecialDaysSchedule": [255],
            "ValidFrom": "2019-01-02 00:00:00", 
            "ValidTo": "2037-01-02 01:00:00"
        }
    ]
}"""
        self.text_json.insert("0.0", default_json)

        self.btn_request = ctk.CTkButton(
            req_card,
            text="ENVIAR REQUISIÇÃO",
            height=38,
            state="disabled",
            fg_color="#2CC985",
            text_color="white",
            hover_color="#24A36B",
            command=self.send_request,
        )
        self.btn_request.grid(
            row=3, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="ew"
        )

        ctk.CTkLabel(
            main_frame, text="Console do Sistema:", font=self.fonts["sub_header"]
        ).grid(row=2, column=0, sticky="w", pady=(0, 5))

        self.text_log = ctk.CTkTextbox(
            main_frame, font=self.fonts["mono"], fg_color="black"
        )
        self.text_log.grid(row=3, column=0, sticky="nsew")

        # Tags de cor
        self.text_log._textbox.tag_config("verde_padrao", foreground="#00FF00")
        self.text_log._textbox.tag_config("amarelo_destaque", foreground="#F1C40F")
        self.text_log._textbox.tag_config("azul_sucesso", foreground="#3498DB")
        self.text_log._textbox.tag_config("vermelho_erro", foreground="#FF5555")
        self.text_log._textbox.tag_config("roxo_evento", foreground="#9B59B6")
        self.text_log._textbox.tag_config("turquesa_sucesso", foreground="#00CED1")
        self.text_log._textbox.tag_config("laranja_aviso", foreground="#FFA500")

    def _create_separator(self, parent, text, row):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=20, pady=(20, 5))
        label = ctk.CTkLabel(
            frame, text=text, font=("Roboto", 11, "bold"), text_color="gray60"
        )
        label.pack(side="left")

    def _create_labeled_entry(self, parent, label_txt, default_val, row, show=None):
        # Frame com rótulo e entrada
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(10, 0), sticky="ew")

        # Label acima
        lbl = ctk.CTkLabel(frame, text=label_txt, font=self.fonts["body"], anchor="w")
        lbl.pack(side="top", fill="x")

        # Entry (com opção de ocultar para password)
        entry = ctk.CTkEntry(frame, show=show)
        entry.pack(side="top", fill="x", pady=(2, 0))
        entry.insert(0, default_val)
        return entry

    # Alterna visibilidade da senha entre * e texto claro
    def toggle_password_visibility(self):
        if self.chk_show_pass.get():
            # Mostrar senha
            self.entry_pass.configure(show="")
        else:
            # Ocultar senha
            self.entry_pass.configure(show="*")

    # Converte logs do backend em texto colorido para exibição na GUI
    def log_to_ui(self, text):
        # Remove prefixo padrão do backend
        text = text.replace("Backend: ", "")
        # Adiciona timestamp formatado
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        full_text = f"{timestamp} {text}"

        tag = "verde_padrao"

        if "Post Eventos" in text:
            tag = "roxo_evento"
        elif "Dados Post Evento 2.0" in text:
            tag = "turquesa_sucesso"
        elif "Dados Post Evento recebido" in text:
            tag = "laranja_aviso"
        elif "POST /cgi-bin/api/autoRegist/connect" in text:
            tag = "amarelo_destaque"
        elif "Login OK!" in text or "Request enviado para" in text:
            tag = "azul_sucesso"
        elif (
            "401 Unauthorized" in text
            or "Erro" in text
            or "WinError" in text
            or "perdeu conexão" in text
            or "Servidor TCP parado" in text
        ):
            tag = "vermelho_erro"

        # Agenda a inserção de texto na thread principal (thread-safe)
        self.after(0, lambda: self._append_log_colored(full_text, tag))

    # Insere texto no log com coloração customizada
    # Destaca portas em amarelo e outras partes em cores específicas
    def _append_log_colored(self, text, body_tag):
        # Regex para capturar tuplas de endereço IP e Porta ('IP', PORTA)
        # Exemplo: "Recebido de ('192.168.1.1', 60002): ..."
        pattern = r"(.* de \('[0-9\.]+', )(\d+)(\).*)"
        parts = re.split(pattern, text, maxsplit=1)

        if len(parts) >= 4:
            # parts[1] = "Recebido de ('IP', " -> Verde
            # parts[2] = "PORTA" -> Amarelo destaque
            # parts[3] = "):..." até o corpo da mensagem -> Verde
            # parts[4] = Corpo (JSON, headers, etc) -> Cor variável

            # Insere prefixo em verde
            self.text_log._textbox.insert("end", parts[1], "verde_padrao")
            # Insere porta em amarelo destaque
            self.text_log._textbox.insert("end", parts[2], "amarelo_destaque")
            # Insere fechamento ") e início da mensagem em verde
            self.text_log._textbox.insert("end", parts[3], "verde_padrao")

            # Corpo da mensagem na cor atribuída
            body_msg = parts[4]
            if body_msg.strip():
                if not body_msg.endswith("\n"):
                    body_msg += "\n"
                self.text_log._textbox.insert("end", body_msg, body_tag)
            else:
                self.text_log._textbox.insert("end", "\n")

        else:
            # Insere linha inteira na cor definida
            self.text_log._textbox.insert("end", text + "\n", body_tag)

        # Rola para o final do texto
        self.text_log.see("end")

    # Altera texto e cor do botão conforme estado
    def toggle_register(self):
        if not self.backend.is_running_register:
            hb_val = self.entry_hb.get().strip()
            use_ssl = bool(self.chk_ssl.get())
            ip_val = self.entry_ip.get().strip()
            port_val = self.entry_port.get().strip()

            self.save_history("ips", ip_val)
            self.save_history("ports", port_val)

            if self.backend.start_listen_auto_register(
                ip_val,
                port_val,
                self.entry_user.get(),
                self.entry_pass.get(),
                heartbeat_interval=hb_val,
                use_ssl=use_ssl,
                cert_file="server.crt",
                key_file="server.key",
            ):
                # Sucesso: altera botão para "Parar"
                self.btn_register.configure(
                    text="PARAR SERVIDOR", fg_color="#FF474C", hover_color="#C22E32"
                )
                # Altera status para "Aguardando Dispositivo"
                self.lbl_status.configure(
                    text="● Aguardando Dispositivo...", text_color="orange"
                )
        else:
            self.backend.stop_listen_auto_register()
            # Reseta botão para "Iniciar"
            self.btn_register.configure(
                text="INICIAR SERVIDOR",
                fg_color=("#3a7ebf", "#1f538d"),
                hover_color=("#325882", "#14375e"),
            )
            # Reseta status para "Desconectado"
            self.lbl_status.configure(text="● Desconectado", text_color="gray")

    # Altera texto e estilo do botão conforme estado
    def toggle_upload(self):
        if not self.backend.is_running_upload:
            prefix_val = self.entry_prefix.get().strip()
            use_ssl = bool(self.chk_ssl_upload.get())

            self.save_history("prefixes", prefix_val)

            if self.backend.start_listen_upload(
                prefix_val,
                use_ssl=use_ssl,
                cert_file="server.crt",
                key_file="server.key",
            ):
                # Sucesso: altera para "Parar"
                self.btn_upload.configure(
                    text="Parar Post Eventos", fg_color="#FF474C", text_color="white"
                )
        else:
            self.backend.stop_listen_upload()
            # Reseta para "Ativar"
            self.btn_upload.configure(
                text="Ativar Post Eventos",
                fg_color="transparent",
                text_color=("gray10", "#DCE4EE"),
            )

    def send_request(self):
        # Obtém Device ID da UI e salva no histórico
        dev_id = self.entry_dev_id.get().strip()
        self.save_history("device_ids", dev_id)

        self.backend.send_request(
            dev_id,
            self.entry_method.get().strip(),
            self.entry_url.get().strip(),
            self.text_json.get("0.0", "end").strip(),
        )

    # Se servidor caiu, reseta botão para "INICIAR SERVIDOR"
    def check_login_status(self):
        # Se servidor TCP não está rodando mas botão ainda mostra "PARAR"
        # significa que desconectou abruptamente - restaura estado da UI
        if (
            not self.backend.is_running_register
            and self.btn_register.cget("text") == "PARAR SERVIDOR"
        ):
            self.btn_register.configure(
                text="INICIAR SERVIDOR",
                fg_color=("#3a7ebf", "#1f538d"),
                hover_color=("#325882", "#14375e"),
            )
            self.lbl_status.configure(text="● Desconectado", text_color="gray")

        # Obtém Device ID da entrada e valida se está logado
        is_logged = self.backend.is_device_login(self.entry_dev_id.get().strip())
        if is_logged:
            # Dispositivo autenticado: ativa botão de requisição com cor verde
            self.btn_request.configure(state="normal", fg_color="#2CC985")
            self.lbl_status.configure(text="● Conectado & Logado", text_color="#2CC985")
        else:
            # Dispositivo não autenticado: desativa botão, cinza
            self.btn_request.configure(state="disabled", fg_color="gray")

        # Agenda próxima verificação em 2 segundos
        self.after(2000, self.check_login_status)
