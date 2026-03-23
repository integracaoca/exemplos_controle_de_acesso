# Servidor Auto CGI - Comentários e Documentação do Código

Este documento resume os comentários adicionados ao projeto **Servidor Auto CGI**, com foco em facilitar a leitura, manutenção e entendimento do fluxo principal da aplicação.

A proposta dos comentários foi explicar o papel de cada parte importante do sistema sem sobrecarregar o código com observações desnecessárias.
---

## Arquivo: `main.py`

### Estrutura Geral
O arquivo principal é dividido em 3 seções principais:

1. **IMPORTAÇÕES** - Documenta cada módulo importado
   - `NetworkManager`: gerenciador de rede
   - `MainApp`: interface gráfica principal
   - `customtkinter`: biblioteca para UI moderna

2. **PONTO DE ENTRADA** - Marca a seção main
   - Apenas executa quando o script é rodado diretamente

3. **CONFIGURAÇÃO DO TEMA** - Detalha as configurações visuais
   - Modo escuro da interface
   - Tema de cores verde

4. **INICIALIZAÇÃO E EXECUÇÃO** - Documenta o fluxo
   - Criação da aplicação com NetworkManager
   - Inicialização do loop principal

---

## Arquivo: `backend.py`

### Classes Principais

#### 1. **HttpBasicInfo**
- Armazena credenciais de autenticação (username e password)
- Usada para autenticação HTTP Digest com dispositivos

#### 2. **DeviceSession**
- Representa uma sessão de conexão com um dispositivo
- Atributos:
  - `socket`: Socket TCP para comunicação
  - `addr`: Endereço IP e porta
  - `token`: Token de autenticação
  - `device_id`: ID único do dispositivo
  - `connected`: Flag de status de conexão
  - `heartbeat_timer`: Thread de keep-alive
  - `missed_heartbeats`: Contador de falhas (máx 3)

#### 3. **NetworkManager**
Gerencia toda a comunicação de rede com dispositivos. Principais responsabilidades:
- Iniciar/parar servidores TCP e HTTP
- Autenticar dispositivos (HTTP Digest)
- Gerenciar logs em múltiplos formatos
- Manter conexões vivas com heartbeat

### Métodos do NetworkManager

#### **_get_base_dir()**
Retorna o diretório base do script para localizar arquivos

#### **_save_event_data(content)**
- Salva eventos recebidos dos dispositivos
- Detecta JSON vs texto simples
- Armazena em `/dados recebidos/`

#### **_save_json_log(content)**
- Salva logs internos com informações sensíveis (Token, DeviceID, etc.)
- Armazena em `/json_log/` para separação de dados sensíveis

#### **log(text, file_text=None)**
Sistema robusto de logging com 3 blocos:
1. **Salva em arquivo** (com timestamp)
2. **Salva JSON separado** se contém Token/DeviceID
3. **Filtra headers HTTP** antes de exibir na GUI
   - Remove headers desnecessários para melhor visualização

#### **_init_log_file(device_id)**
- Inicializa arquivo de log após conexão do dispositivo
- Despeja buffer de logs coletados antes
- Cria diretório `/log/` se necessário

#### **calculate_md5(input_str)**
Calcula hash MD5 para autenticação HTTP Digest

#### **_extract_regex(text, pattern)**
Extrai valores de strings usando regex com grupos de captura

#### **generate_auth_response(...)**
Implementa RFC 2617 para gerar resposta de autenticação Digest:
1. HA1 = MD5(username:realm:password)
2. HA2 = MD5(method:uri)
3. Response = MD5(HA1:nonce:nc:cnonce:qop:HA2)

#### **start_listen_auto_register(...)**
Inicia servidor TCP para registro automático. Blocos principais:
1. **Criação do socket** - TCP bruto com SO_REUSEADDR e SO_KEEPALIVE
2. **Aplicação de SSL/TLS** - Se solicitado, envolve socket com SSL
3. **Inicia thread** - Thread daemon para aceitar conexões

#### **stop_listen_auto_register()**
Para servidor e encerra todas as conexões:
- Marca `is_running_register = False`
- Fecha socket do servidor
- Encerra todas as DeviceSession
- Limpa mapas

#### **_listen_connect_socket()**
Loop que aceita novas conexões de dispositivos:
- Aguarda conexões
- Cria DeviceSession para cada dispositivo
- Inicia thread para processar respostas

#### **_handle_client_response(session)**
Processa mensagens de um dispositivo. Blocos principais:
1. **Reseta heartbeat** - Se receber dados válidos
2. **Conexão inicial** - Processa `/cgi-bin/api/autoRegist/connect`
3. **Autenticação Digest** - Responde a `401 Unauthorized`
4. **Token recebido** - Inicia heartbeat após login bem-sucedido

#### **_start_heartbeat(session)**
Thread que mantém conexão viva. Blocos:
1. **Sleep** - Aguarda intervalo configurado
2. **Verifica falhas** - Se 3 falhas consecutivas, desconecta
3. **Incrementa contador** - Pessimista (assume falha)
4. **Envia keep-alive** - POST `/cgi-bin/api/global/keep-alive`

#### **send_request(device_id, method, uri, data)**
Envia requisição HTTP customizada para dispositivo:
- Valida se dispositivo está autenticado
- Normaliza quebras de linha no corpo
- Envia com token de autenticação
- Registra detalhes em arquivo

#### **is_device_login(device_id)**
Verifica se dispositivo está autenticado

#### **start_listen_upload(prefix_url, use_ssl, cert_file, key_file)**
Inicia servidor HTTP para receber POSTs de eventos. Recursos:
1. **Extração de porta** - Da URL fornecida
2. **RequestHandler interna** - Processa POST e GET
3. **Validação JSON** - Detecta e salva em formato apropriado
4. **Suporte SSL/TLS** - Opcional

#### **stop_listen_upload()**
Para servidor HTTP de eventos

---

## Estrutura de Diretórios de Logs

```
/log/                    - Arquivos de log principais (por dispositivo)
/json_log/              - Logs com dados sensíveis de autenticação
/dados recebidos/       - Eventos POST recebidos dos dispositivos
```

---

## Fluxo de Autenticação

1. Dispositivo conecta → envia `/autoRegist/connect` com DeviceID
2. Servidor responde com 200 OK
3. Servidor envia POST `/global/login`
4. Dispositivo responde com 401 Unauthorized + parâmetros Digest
5. Servidor calcula response Digest e envia novamente
6. Dispositivo responde com Token
7. Servidor inicia heartbeat a cada N segundos
8. Resposta 200 OK reseta contador de falhas
9. 3 falhas consecutivas = desconexão

---

## Fluxo de Heartbeat

```
Sleep (N segundos)
    ↓
Verifica se 3 falhas → Desconecta
    ↓
Incrementa contador (pessimista)
    ↓
Tenta enviar POST /keep-alive
    ↓
Se recebe resposta 200 → Reseta contador
Se falha → Continua loop (não mata servidor)
```

---

## Características Principais

### Robustez
- Não mata servidor se dispositivo desconectar
- Permite heartbeat tentar 3 vezes antes de desistir
- Tratamento de erros em todos os pontos críticos

### Logging Detalhado
- Logs em arquivo + GUI
- Separação de dados sensíveis
- Detecção automática de formato (JSON vs TXT)
- Headers HTTP filtrados na GUI

### Segurança
- Autenticação HTTP Digest (RFC 2617)
- Suporte a SSL/TLS opcional
- Tokens de autenticação por sessão

### Performance
- Operações em threads separadas
- Não-bloqueante para UI
- Keep-alive para manter conexões estáveis

---

**Projeto:** API-Intelbras - Servidor Auto CGI 
**Linguagem:** Python 3.x  
**Data:** Novembro 2025
