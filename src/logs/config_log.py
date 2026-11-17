import logging 
import os


def configurar_logger():

    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    diretorio_raiz = os.path.abspath(os.path.join(diretorio_atual, "../../"))

    pasta = "Logs"

    caminho_pasta = os.path.join(diretorio_raiz, pasta)

    if not os.path.exists(caminho_pasta):
        os.makedirs(caminho_pasta, exist_ok=True)


    logger = logging.getLogger("Safe-Track")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:

        
        caminho_debug = os.path.join(caminho_pasta, 'debug.log')
        caminho_error = os.path.join(caminho_pasta, 'error.log')

        handler_terminal = logging.StreamHandler() ##Aqui o StreamHandler diz exiba no terminal por isso eu acabei de batizar ele como handler_terminal
        handler_arq_debug = logging.FileHandler(caminho_debug) # Agora salva dentro de src/Logs
        handler_arq_error = logging.FileHandler(caminho_error) # Agora salva dentro de src/Logs



        handler_terminal.setLevel(logging.DEBUG)
        handler_arq_debug.setLevel(logging.DEBUG)
        handler_arq_error.setLevel(logging.ERROR)

        formato_mensagem = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
        handler_terminal.setFormatter(formato_mensagem)
        handler_arq_debug.setFormatter(formato_mensagem)
        handler_arq_error.setFormatter(formato_mensagem)

        logger.addHandler(handler_terminal)
        logger.addHandler(handler_arq_debug)
        logger.addHandler(handler_arq_error)


    return logger
