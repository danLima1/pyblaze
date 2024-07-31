import logging
import asyncio
import requests
from pyrogram import Client, filters
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("bot_log.log"),
    logging.StreamHandler()
])

# Configuração do Pyrogram
api_id = '24302231'
api_hash = '37d4966f5f5c1a949511be2a4cc8e41a'
bot_token = '7104858857:AAFrDv1JZEuHnnGozhbMd1l858G-mvRLiRE'
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Banco de dados fake
fake_db = {}
user_states = {}  # Dicionário para armazenar o estado do usuário
group_chat_id = -1002235935199  # Substitua pelo chat_id do grupo de onde os sinais virão

# Variáveis globais para sinais
sinal_resultado = ''
sinal_analise = False
sinal_cor = ''
sinal_id = None  # ID do sinal para garantir que Martingale ocorra apenas uma vez por sinal

# Armazenar as informações dos usuários
user_bets = {}


def login_blaze(email, password):
    driver = webdriver.Chrome()
    driver.get('https://blaze.com')
    time.sleep(3)

    # Clica no botão de login
    driver.find_element(By.XPATH, '//*[@id="header"]/div/div[2]/div/div/div[1]/a').click()
    time.sleep(2)

    # Entra o email
    driver.find_element(By.XPATH, '//*[@id="auth-modal"]/div/form/div[1]/div/input').send_keys(email)
    time.sleep(1)

    # Entra a senha
    driver.find_element(By.XPATH, '//*[@id="auth-modal"]/div/form/div[2]/div/input').send_keys(password)
    time.sleep(1)

    # Clica no botão de entrar
    driver.find_element(By.XPATH, '//*[@id="auth-modal"]/div/form/div[4]/button').click()
    time.sleep(5)

    # Acessa o jogo double
    driver.get('https://blaze.com/pt/games/double')
    time.sleep(5)

    return driver


@app.on_message(filters.command("start"))
async def send_welcome(client, message):
    await message.reply("Bem-vindo ao bot! Para fazer suas apostas automáticas clique em /login")


@app.on_message(filters.command("login"))
async def get_email(client, message):
    chat_id = message.chat.id
    user_states[chat_id] = 'awaiting_email'
    await message.reply("Por favor, forneça o endereço de email da sua conta Blaze:")


@app.on_message(filters.text)
async def handle_messages(client, message):
    global sinal_resultado, sinal_id
    chat_id = message.chat.id

    # Verifica se a mensagem é do grupo específico
    if chat_id == group_chat_id:
        message_text = message.text
        logging.info(f"Mensagem recebida no grupo {chat_id}: {message_text}")
        if 'Entrar agora' in message_text:
            sinal_resultado = message_text  # Atualiza a variável global 'resultado'
            sinal_id = int(time.time())  # Usa timestamp como ID do sinal
            logging.info(f"Novo sinal recebido: {sinal_resultado}")
            # Inicia o processo de aposta
            loop = asyncio.get_event_loop()
            for user in user_bets.keys():
                loop.run_in_executor(None, handle_bet, user, user_bets[user]['driver'], sinal_id)
        return

    # Processo de login e configuração da aposta
    if chat_id in user_states:
        state = user_states[chat_id]

        if state == 'awaiting_email':
            email = message.text
            fake_db[chat_id] = {'email': email}
            user_states[chat_id] = 'awaiting_password'
            await message.reply("Agora, por favor, forneça a senha:")

        elif state == 'awaiting_password':
            password = message.text
            fake_db[chat_id]['password'] = password
            user_states[chat_id] = 'awaiting_color_bet_amount'
            await message.reply("Login efetuado com sucesso! Agora, por favor, forneça o valor da aposta para cores:")

        elif state == 'awaiting_color_bet_amount':
            color_bet_amount = float(message.text)
            fake_db[chat_id]['color_bet_amount'] = color_bet_amount
            user_states[chat_id] = 'awaiting_white_bet_amount'
            await message.reply("Agora, por favor, forneça o valor da aposta para a cor branca:")

        elif state == 'awaiting_white_bet_amount':
            white_bet_amount = float(message.text)
            fake_db[chat_id]['white_bet_amount'] = white_bet_amount
            user_states[chat_id] = 'awaiting_color_gale_amount'
            await message.reply("Por favor, forneça o valor do Gale para cores:")

        elif state == 'awaiting_color_gale_amount':
            color_gale_amount = float(message.text)
            fake_db[chat_id]['color_gale_amount'] = color_gale_amount
            user_states[chat_id] = 'awaiting_white_gale_amount'
            await message.reply("Por favor, forneça o valor do Gale para a cor branca:")

        elif state == 'awaiting_white_gale_amount':
            white_gale_amount = float(message.text)
            fake_db[chat_id]['white_gale_amount'] = white_gale_amount
            user_bets[chat_id] = {
                'color_bet_amount': fake_db[chat_id]['color_bet_amount'],
                'current_color_bet_amount': fake_db[chat_id]['color_bet_amount'],
                'white_bet_amount': fake_db[chat_id]['white_bet_amount'],
                'color_gale_amount': fake_db[chat_id]['color_gale_amount'],
                'white_gale_amount': fake_db[chat_id]['white_gale_amount'],
                'current_white_bet_amount': fake_db[chat_id]['white_bet_amount'],
                'email': fake_db[chat_id]['email'],
                'password': fake_db[chat_id]['password'],
                'driver': None  # Será inicializado posteriormente
            }
            await message.reply('Valores da aposta e do Gale recebidos! Iniciando o processo de apostas...')

            # Inicia o Selenium e faz login em uma thread separada
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, selenium_logic, chat_id)
            del user_states[chat_id]


def selenium_logic(chat_id):
    user_info = user_bets[chat_id]
    email = user_info['email']
    password = user_info['password']
    driver = login_blaze(email, password)
    user_bets[chat_id]['driver'] = driver
    handle_bet(chat_id, driver, None)


def handle_bet(chat_id, driver, signal_id):
    global sinal_resultado, sinal_analise, sinal_cor, sinal_id
    user_info = user_bets[chat_id]

    if signal_id is not None and sinal_id != signal_id:
        return

    if sinal_resultado:
        estrategy(sinal_resultado)

        if sinal_analise:
            # Define os valores de aposta
            color_bet_amount = str(user_info['current_color_bet_amount'])
            white_bet_amount = str(user_info['current_white_bet_amount'])

            # Primeiro aposta na cor especificada
            bet_input = driver.find_element(By.XPATH,
                                            '//*[@id="roulette-controller"]/div[1]/div[2]/div[1]/div/div[1]/input')
            try:
                bet_input.clear()
            except:
                return
            bet_input.send_keys(color_bet_amount)
            logging.info('Valor da aposta para cor definido')
            time.sleep(1)

            color_button_xpath = '//*[@id="roulette-controller"]/div[1]/div[2]/div[2]/div/div[3]' if sinal_cor == '⚫️' else '//*[@id="roulette-controller"]/div[1]/div[2]/div[2]/div/div[1]'
            color_button = driver.find_element(By.XPATH, color_button_xpath)

            try:
                color_button.click()
                logging.info('Botão de cor apertado')
            except:
                return
            time.sleep(1)

            try:
                confirm_button_xpath = '//*[@id="roulette-controller"]/div[1]/div[3]/button'
                confirm_button = driver.find_element(By.XPATH, confirm_button_xpath)
                confirm_button.click()
                logging.info('Aposta confirmada')
            except:
                return
            time.sleep(1)

            # Depois aposta na cor branca
            try:
                bet_input.clear()
            except:
                return
            bet_input.send_keys(white_bet_amount)
            logging.info('Valor da aposta para cor branca definido')
            time.sleep(1)

            white_button_xpath = '//*[@id="roulette-controller"]/div[1]/div[2]/div[2]/div/div[2]'
            white_button = driver.find_element(By.XPATH, white_button_xpath)

            try:
                white_button.click()
                logging.info('Botão da cor branca apertado')
            except:
                return
            time.sleep(1)

            try:
                confirm_button.click()
                logging.info('Aposta na cor branca confirmada')
            except:
                return
            time.sleep(1)

            # Espera pelo resultado da aposta
            time.sleep(24)
            resultado_api = get_recent_results()
            logging.info(f'Resultado da API: {resultado_api}')

            if resultado_api:
                last_color = resultado_api[0]['color']
                if last_color == 0 or (sinal_cor == '⚫️' and last_color == 2) or (sinal_cor == '🔴' and last_color == 1):
                    # Aposta ganha, reseta os valores da aposta
                    user_info['current_color_bet_amount'] = user_info['color_bet_amount']
                    user_info['current_white_bet_amount'] = user_info['white_bet_amount']
                    logging.info('Aposta ganha, valores da aposta resetados')
                else:
                    if sinal_id == signal_id:
                        # Aposta perdida, utiliza o valor do Gale configurado
                        user_info['current_color_bet_amount'] = user_info['color_gale_amount']
                        user_info['current_white_bet_amount'] = user_info['white_gale_amount']
                        logging.info(
                            f"Aposta perdida, novos valores da aposta: {user_info['current_color_bet_amount']} para cores e {user_info['current_white_bet_amount']} para branco")

                        # Refaz a aposta com os valores de Gale
                        # Aposta na cor especificada
                        bet_input.clear()
                        bet_input.send_keys(str(user_info['current_color_bet_amount']))
                        logging.info('Valor da aposta redefinido')
                        time.sleep(1)

                        try:
                            color_button.click()
                            logging.info('Botão de cor apertado novamente')
                        except:
                            return
                        time.sleep(1)

                        try:
                            confirm_button.click()
                            logging.info('Aposta confirmada novamente')
                        except:
                            return
                        time.sleep(1)

                        # Aposta na cor branca
                        bet_input.clear()
                        bet_input.send_keys(str(user_info['current_white_bet_amount']))
                        logging.info('Valor da aposta para branco redefinido')
                        time.sleep(1)

                        try:
                            white_button.click()
                            logging.info('Botão da cor branca apertado novamente')
                        except:
                            return
                        time.sleep(1)

                        try:
                            confirm_button.click()
                            logging.info('Aposta na cor branca confirmada novamente')
                        except:
                            return
                        time.sleep(1)

                        # Após o Martingale, reseta os valores da aposta aos valores originais
                        user_info['current_color_bet_amount'] = user_info['color_bet_amount']
                        user_info['current_white_bet_amount'] = user_info['white_bet_amount']
                        logging.info('Após o Martingale, valores da aposta resetados aos valores originais')


def get_recent_results():
    try:
        response = requests.get('https://blaze.com/api/roulette_games/recent')
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f'Erro ao acessar a API: {response.status_code}')
            return None
    except Exception as e:
        logging.error(f'Erro ao acessar a API: {e}')
        return None


def estrategy(signal):
    global sinal_analise, sinal_cor
    if 'Entrar agora: 🔴 + ⚪️' in signal:
        sinal_cor = '🔴'
        sinal_analise = True
    elif 'Entrar agora: ⚫️ + ⚪️' in signal:
        sinal_cor = '⚫️'
        sinal_analise = True
    else:
        sinal_analise = False


app.run()
