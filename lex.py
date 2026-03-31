p_reservadas = ["class", "else", "false", "fi", "if", "in", "inherits", "isvoid", "let", "loop", "pool", 
                "then", "while", "case", "esac", "new", "of", "not", "true"]
 
lst_read = None
dentro_string = False

def pega_char(arq):
    global lst_read
    if lst_read:
        res = lst_read
        lst_read = None
        return res
    return arq.read(1)

def lexico(arq):
    global lst_read, dentro_string
    palavra = "" 
    
    while True:
        c = pega_char(arq)
        if not c:
            return palavra if palavra else None
    
        if c == '"':
            if palavra:
                lst_read = '"'
                return palavra
            dentro_string = not dentro_string
            return c 
        
        if dentro_string:
            proximo = arq.read(1)
            if proximo == '"':
                palavra += c
                if proximo:
                    arq.seek(arq.tell() - 1)
                return palavra
            else:
                if proximo:
                    arq.seek(arq.tell() - 1)
                palavra += c
                continue
            
        if c.isalpha() or c.isdigit() or c == "_" or c == ".":
            palavra += c
            continue

        if c.isspace():
            if palavra:
                return palavra
            continue
        
        if c == "(":
            proximo = pega_char(arq)
            if proximo == "*":
                while True:
                    char_com = arq.read(1)
                    if not char_com: break
                    if char_com == "*":
                        if arq.read(1) == ")": break
                    if palavra: return palavra
                    else: continue
            else:
                if palavra: #Caso não seja comentário
                    lst_read = "(" 
                    if proximo:
                        arq.seek(arq.tell() - 1) 
                    return palavra
                if proximo:
                    arq.seek(arq.tell() - 1)
                return "("
        

        if c == "-":
            proximo = pega_char(arq)
            if proximo == "-":
                while True:
                    char_com = arq.read(1)
                    if not char_com: break
                    if char_com == "\n": break
                    if palavra: return palavra
                    else: continue
        if c == "<":
            if palavra:
                lst_read = "<"
                return palavra
            proximo = pega_char(arq)
            if proximo == "-" : return "<-"
            else:
                lst_read = proximo
                return "<"
            
        if c == "=":
            if palavra:
                lst_read = "="
                return palavra
            proximo = pega_char(arq)
            if proximo == ">" : return "=>"
            else:
                lst_read = proximo
                return "="

        #Retorna um simbolo caso não seja uma palavra ou um caractere que requer atenção 
        if palavra:
            lst_read = c
            return palavra
        return c

def main():
    with open("teste.txt", "r") as arquivo:

        p = lexico(arquivo)
        while(p):
            print("Token: " + p)
            p = lexico(arquivo)
        
main()
