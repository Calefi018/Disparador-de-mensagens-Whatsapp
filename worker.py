import time
import os
import urllib.parse
from celery import Celery
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- Configuração ---
# O worker precisa saber sobre o app Flask para ter o contexto de configuração
from app import app

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# O caminho para a sessão do Chrome agora aponta para o disco persistente do Render
CHROME_SESSION_PATH = "/var/data/chrome_session"


@celery.task
def enviar_para_lista(numeros, mensagem, intervalo):
    chrome_options = Options()
    # Opções essenciais para rodar o Chrome em um ambiente de servidor/Docker
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Aponta para a pasta de sessão no disco persistente
    chrome_options.add_argument(f"user-data-dir={CHROME_SESSION_PATH}")

    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        print("Driver do Chrome iniciado com sucesso.")

        for numero in numeros:
            try:
                texto_formatado = urllib.parse.quote(mensagem)
                url = f"https://web.whatsapp.com/send?phone={numero}&text={texto_formatado}"
                driver.get(url)

                # Aumenta o tempo de espera para dar conta de conexões mais lentas no servidor
                wait = WebDriverWait(driver, 90)
                
                # Espera pelo botão de enviar. XPath robusto.
                send_button_xpath = '//span[@data-icon="send"]'
                send_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, send_button_xpath))
                )
                
                time.sleep(2)  # Pausa extra antes de clicar
                send_button.click()
                print(f"Mensagem enviada para {numero}")
                
                time.sleep(intervalo)
            
            except Exception as e:
                print(f"Falha ao enviar para {numero}: {e}")
                # Salva um screenshot para ajudar a depurar (será salvo no sistema de arquivos temporário)
                driver.save_screenshot(f'error_{numero}.png')

    except Exception as e:
        print(f"Ocorreu um erro crítico no worker: {e}")
    finally:
        if driver:
            driver.quit()
        print("Campanha finalizada.")
    
    return "Processo de envio concluído."