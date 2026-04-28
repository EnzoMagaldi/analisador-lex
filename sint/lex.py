p_reservadas = ["class", "else", "false", "fi", "if", "in", "inherits", "isvoid", "let", "loop", "pool", 
                "then", "while", "case", "esac", "new", "of", "not", "true"]

operador = ["+", "-", "*", "/", "=", "<"]

tipos = {
    "RESERVADA": "RESERVADA",
    "INTEIRO": "INTEIRO",
    "STRING": "STRING",
    "IDENTIFICADOR": "IDENTIFICADOR",
    "SIMBOLO" : "SIMBOLO",
    "OPERADOR": "OPERADOR",
}

identificador = []
lst_read = None
linha = 1

def pega_char(arq):
    global lst_read, linha
    if lst_read:
        res = lst_read
        lst_read = None
        return res
    
    c = arq.read(1)
    if c == "\n":
        linha += 1 # Incrementa apenas quando lê do disco
    return c

def processa_palavra(palavra, linha):
    if palavra.lower() in p_reservadas:
        return (linha, tipos["RESERVADA"], palavra.lower())
    if palavra.isdigit():
        return (linha, tipos["INTEIRO"], palavra)
    else:
        if palavra not in identificador:
            identificador.append(palavra)
        return (linha, tipos["IDENTIFICADOR"], palavra)

def lexico(arq):
    global lst_read, identificador, linha
    palavra = "" 
    
    while True:
        c = pega_char(arq)
        if not c:
            if palavra:
                return processa_palavra(palavra, linha)
            return None

        if c.isalpha() or c.isdigit() or c == "_":
            palavra += c
            continue
        
        if palavra:
            lst_read = c
            return processa_palavra(palavra, linha)

        if c.isspace():
            continue

        if c == '"':
            conteudo = ""
            while True:
                ch = arq.read(1)
                if not ch or ch == '"':
                    break
                if ch == '\n':
                    linha += 1
                conteudo += ch
            return (linha, tipos["STRING"], conteudo)
        
        if c == "(":
            proximo = pega_char(arq)
            if proximo == "*":
                profundidade = 1
                ultimo = ""
                while profundidade > 0:
                    char_com = arq.read(1)
                    if not char_com:
                        break
                    if char_com == "\n":
                        linha += 1
                    if ultimo == "(" and char_com == "*":
                        profundidade += 1
                        ultimo = ""
                    elif ultimo == "*" and char_com == ")":
                        profundidade -= 1
                        ultimo = ""
                    else:
                        ultimo = char_com
                continue 
            else:
                lst_read = proximo
                return (linha, tipos["SIMBOLO"], "(")

        if c == "-":
            proximo = pega_char(arq)
            if proximo == "-":
                while True:
                    char_com = arq.read(1)
                    if not char_com or char_com == "\n":
                        if char_com == "\n":
                            linha += 1
                        break
                continue  
            else:
                lst_read = proximo
                return (linha, tipos["OPERADOR"], "-")
                    
        if c == "<":
            proximo = pega_char(arq)
            if proximo == "-":
                return (linha, tipos["SIMBOLO"], "<-")
            else:
                lst_read = proximo
                return (linha, tipos["OPERADOR"], "<")
            
        if c == "=":
            proximo = pega_char(arq)
            if proximo == ">":
                return (linha, tipos["SIMBOLO"], "=>")
            else:
                lst_read = proximo
                return (linha, tipos["OPERADOR"], "=")

        if c in operador:
            return (linha, tipos["OPERADOR"], c)

        return (linha, tipos["SIMBOLO"], c)

'''def main():
    try:
        with open("teste.txt", "r") as arquivo:
            token = lexico(arquivo)
            while token:
                print(token)
                token = lexico(arquivo)
    except FileNotFoundError:
        print("Arquivo teste.txt não encontrado.")
        
if __name__ == "__main__":
    main()'''
