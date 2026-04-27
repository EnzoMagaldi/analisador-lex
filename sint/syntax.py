from dataclasses import dataclass, field
from typing import Optional, List, Any
from lex import lexico, tipos

@dataclass
class ProgramNode:
    classes: List['ClassNode']

@dataclass
class ClassNode:
    name: str
    parent: Optional[str]
    features: List
    linha: int

@dataclass
class AttributeNode:
    name: str
    type_: str
    init: Optional[Any]
    linha: int

@dataclass
class MethodNode:
    name: str
    formals: List['FormalNode']
    return_type: str
    body: Any
    linha: int

@dataclass
class FormalNode:
    name: str
    type_: str

@dataclass
class AssignNode:
    name: str
    value: Any
    linha: int

@dataclass
class DispatchNode:
    obj: Any
    static_type: Optional[str]
    method: str
    args: List
    linha: int

@dataclass
class SelfDispatchNode:
    method: str
    args: List
    linha: int

@dataclass
class IfNode:
    cond: Any
    then_: Any
    else_: Any
    linha: int

@dataclass
class WhileNode:
    cond: Any
    body: Any
    linha: int

@dataclass
class BlockNode:
    exprs: List
    linha: int

@dataclass
class LetBindingNode:
    name: str
    type_: str
    init: Optional[Any]

@dataclass
class LetNode:
    bindings: List['LetBindingNode']
    body: Any
    linha: int

@dataclass
class CaseBranchNode:
    name: str
    type_: str
    body: Any

@dataclass
class CaseNode:
    expr: Any
    branches: List['CaseBranchNode']
    linha: int

@dataclass
class NewNode:
    type_: str
    linha: int

@dataclass
class BinOpNode:
    op: str
    left: Any
    right: Any
    linha: int

@dataclass
class UnaryOpNode:
    op: str
    expr: Any
    linha: int

@dataclass
class IntNode:
    value: int
    linha: int

@dataclass
class StrNode:
    value: str
    linha: int

@dataclass
class BoolNode:
    value: bool
    linha: int

@dataclass
class IdNode:
    name: str
    linha: int

class TokenStream:
    def __init__(self, arquivo):
        self._tokens = []
        self._pos = 0
        self._carregar(arquivo)

    def _carregar(self, arquivo):
        """Lê todos os tokens do lexer de uma vez e normaliza para tupla."""
        while True:
            tok = lexico(arquivo)
            if tok is None:
                break
            if isinstance(tok, tuple):
                self._tokens.append(tok)

    def peek(self):
        """Retorna o próximo token sem consumir. None se acabou."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def consume(self):
        """Consome e retorna o próximo token."""
        tok = self.peek()
        self._pos += 1
        return tok

    def pushback(self, tok):
        """Devolve o último token consumido."""
        self._pos -= 1

    def peek_val(self):
        tok = self.peek()
        return tok[2] if tok else None

    def peek_tipo(self):
        tok = self.peek()
        return tok[1] if tok else None

    def peek_linha(self):
        tok = self.peek()
        return tok[0] if tok else 0

    def is_val(self, valor):
        return self.peek_val() == valor

    def is_tipo(self, tipo):
        return self.peek_tipo() == tipo

    def expect_val(self, valor):
        """Consome o token esperado pelo valor ou lança SyntaxError."""
        tok = self.consume()
        if tok is None or tok[2] != valor:
            encontrado = tok[2] if tok else "fim do arquivo"
            linha = tok[0] if tok else "?"
            raise SyntaxError(
                f"[Linha {linha}] Esperado '{valor}', encontrado '{encontrado}'"
            )
        return tok

    def expect_tipo(self, tipo):
        """Consome o token esperado pelo tipo ou lança SyntaxError."""
        tok = self.consume()
        if tok is None or tok[1] != tipo:
            encontrado = f"{tok[1]}('{tok[2]}')" if tok else "fim do arquivo"
            linha = tok[0] if tok else "?"
            raise SyntaxError(
                f"[Linha {linha}] Esperado tipo '{tipo}', encontrado {encontrado}"
            )
        return tok

class Parser:
    def __init__(self, ts: TokenStream):
        self.ts = ts
        self.erros = []   # acumula todos os erros encontrados


    def _registra_erro(self, mensagem):
        """Adiciona um erro à lista sem interromper o parsing."""
        self.erros.append(mensagem)

    def _sincroniza(self, ate=(";")):
        """
        Avança tokens até encontrar um dos símbolos de sincronização.
        Isso permite que o parser retome após um erro e continue
        reportando outros erros mais adiante no código.
        """
        while self.ts.peek() is not None:
            if self.ts.peek_val() in ate:
                self.ts.consume()
                break
            self.ts.consume()

    #program ::= class+
    def parse_program(self):
        classes = []
        while self.ts.peek() is not None:
            try:
                c = self.parse_class()
                if c is not None:
                    classes.append(c)
            except SyntaxError as e:
                self._registra_erro(str(e))
                # Sincroniza até o próximo ';' ou 'class' para tentar
                # passeia a próxima classe
                self._sincroniza(ate=(";", "class"))
        return ProgramNode(classes)

    #class ::= CLASS TYPE [ INHERITS TYPE ] { feature* } ;
    def parse_class(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("class")

        tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        name = tok_name[2]

        parent = None
        if self.ts.is_val("inherits"):
            self.ts.consume()
            tok_parent = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
            parent = tok_parent[2]

        self.ts.expect_val("{")
        features = []
        while self.ts.peek() is not None and not self.ts.is_val("}"):
            f = self.parse_feature()
            if f is not None:
                features.append(f)
        self.ts.expect_val("}")
        self.ts.expect_val(";")

        return ClassNode(name, parent, features, linha)

    #feature ::= attribute | method
    #A distinção é feita logo após o nome:
    #ID (        -> método:   ID ( formals ) : TYPE { expr } ;
    #ID : TYPE   -> atributo: ID : TYPE [ <- expr ] ;
    def parse_feature(self):
        linha = self.ts.peek_linha()
        try:
            tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
            name = tok_name[2]

            if self.ts.is_val("("):
                # É método — o ": TYPE" vem depois dos parênteses
                return self._parse_method_resto(name, linha)
            else:
                # É atributo — o ": TYPE" vem logo após o nome
                self.ts.expect_val(":")
                tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
                return self._parse_atributo_resto(name, tok_type[2], linha)

        except SyntaxError as e:
            self._registra_erro(str(e))
            self._sincroniza(ate=(";",))
            return None

    def _parse_atributo_resto(self, name, type_, linha):
        init = None
        if self.ts.is_val("<-"):
            self.ts.consume()
            init = self.parse_expr()
        self.ts.expect_val(";")
        return AttributeNode(name, type_, init, linha)

    def _parse_method_resto(self, name, linha):
        self.ts.expect_val("(")
        formals = []
        if not self.ts.is_val(")"):
            formals.append(self._parse_formal())
            while self.ts.is_val(","):
                self.ts.consume()
                formals.append(self._parse_formal())
        self.ts.expect_val(")")
        self.ts.expect_val(":")           # ": TYPE" vem depois do ")"
        tok_ret = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val("{")
        body = self.parse_expr()
        self.ts.expect_val("}")
        self.ts.expect_val(";")
        return MethodNode(name, formals, tok_ret[2], body, linha)

    # formal ::= ID : TYPE
    def _parse_formal(self):
        tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val(":")
        tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        return FormalNode(tok_name[2], tok_type[2])

    #Expressões: hierarquia de precedência (menor → maior)
    #parse_expr      atribuição <-
    #parse_not       NOT
    #parse_compare   < <= =
    #parse_add       + -
    #parse_mul       * /
    #parse_unary     ~ isvoid
    #parse_dispatch  . @
    #parse_atom      literais, if, while, let, case, new, ID, ( expr )
    def parse_expr(self):
        """
        Tenta passear uma atribuição: ID <- expr
        Se o token seguinte ao ID não for '<-', devolve o ID com pushback
        e sobe para parse_not.
        """
        if self.ts.is_tipo(tipos["IDENTIFICADOR"]):
            linha = self.ts.peek_linha()
            tok = self.ts.consume()
            if self.ts.is_val("<-"):
                self.ts.consume()
                value = self.parse_expr()   # associa à direita
                return AssignNode(tok[2], value, linha)
            else:
                self.ts.pushback(tok)       # não era atribuição

        return self.parse_not()

    def parse_not(self):
        if self.ts.is_val("not"):
            linha = self.ts.peek_linha()
            self.ts.consume()
            return UnaryOpNode("not", self.parse_not(), linha)
        return self.parse_compare()

    def parse_compare(self):
        """< <= = são não-associativos em COOL — não encadeiam."""
        left = self.parse_add()
        if self.ts.peek_val() in ("<", "<=", "="):
            linha = self.ts.peek_linha()
            op = self.ts.consume()[2]
            right = self.parse_add()
            return BinOpNode(op, left, right, linha)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.ts.peek_val() in ("+", "-"):
            linha = self.ts.peek_linha()
            op = self.ts.consume()[2]
            right = self.parse_mul()
            left = BinOpNode(op, left, right, linha)
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.ts.peek_val() in ("*", "/"):
            linha = self.ts.peek_linha()
            op = self.ts.consume()[2]
            right = self.parse_unary()
            left = BinOpNode(op, left, right, linha)
        return left

    def parse_unary(self):
        linha = self.ts.peek_linha()
        if self.ts.is_val("~"):
            self.ts.consume()
            return UnaryOpNode("~", self.parse_unary(), linha)
        if self.ts.is_val("isvoid"):
            self.ts.consume()
            return UnaryOpNode("isvoid", self.parse_unary(), linha)
        return self.parse_dispatch()

    def parse_dispatch(self):
        """Dispatch encadeia à esquerda: expr.m(args) ou expr@T.m(args)"""
        left = self.parse_atom()
        while self.ts.is_val(".") or self.ts.is_val("@"):
            linha = self.ts.peek_linha()
            static_type = None
            if self.ts.is_val("@"):
                self.ts.consume()
                static_type = self.ts.consume()[2]
            self.ts.expect_val(".")
            tok_method = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
            args = self._parse_arglist()
            left = DispatchNode(left, static_type, tok_method[2], args, linha)
        return left

    def parse_atom(self):
        """Nível mais alto de precedência — literais e construções atômicas."""
        tok = self.ts.peek()
        if tok is None:
            raise SyntaxError("Fim inesperado do arquivo")

        val  = tok[2]
        tipo = tok[1]
        linha = tok[0]

        if val == "if":    return self._parse_if()
        if val == "while": return self._parse_while()
        if val == "let":   return self._parse_let()
        if val == "case":  return self._parse_case()

        if val == "new":
            self.ts.consume()
            tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
            return NewNode(tok_type[2], linha)

        if val == "{":
            return self._parse_block()

        if val == "(":
            self.ts.consume()
            e = self.parse_expr()
            self.ts.expect_val(")")
            return e

        if val == "true":
            self.ts.consume()
            return BoolNode(True, linha)

        if val == "false":
            self.ts.consume()
            return BoolNode(False, linha)

        if tipo == tipos["INTEIRO"]:
            self.ts.consume()
            return IntNode(int(val), linha)

        if tipo == tipos["STRING"]:
            self.ts.consume()
            return StrNode(val, linha)

        if tipo == tipos["IDENTIFICADOR"]:
            self.ts.consume()
            # ID seguido de '(' é dispatch sobre self
            if self.ts.is_val("("):
                args = self._parse_arglist()
                return SelfDispatchNode(val, args, linha)
            return IdNode(val, linha)

        raise SyntaxError(f"[Linha {linha}] Token inesperado: '{val}'")

    #if ::= IF expr THEN expr ELSE expr FI
    def _parse_if(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("if")
        cond  = self.parse_expr()
        self.ts.expect_val("then")
        then_ = self.parse_expr()
        self.ts.expect_val("else")
        else_ = self.parse_expr()
        self.ts.expect_val("fi")
        return IfNode(cond, then_, else_, linha)

    #while ::= WHILE expr LOOP expr POOL
    def _parse_while(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("while")
        cond = self.parse_expr()
        self.ts.expect_val("loop")
        body = self.parse_expr()
        self.ts.expect_val("pool")
        return WhileNode(cond, body, linha)

    #block ::= { expr ; (expr ;)* }
    def _parse_block(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("{")
        exprs = []
        while self.ts.peek() is not None and not self.ts.is_val("}"):
            try:
                exprs.append(self.parse_expr())
                self.ts.expect_val(";")
            except SyntaxError as e:
                self._registra_erro(str(e))
                self._sincroniza(ate=(";", "}"))
        self.ts.expect_val("}")
        return BlockNode(exprs, linha)

    # let ::= LET ID:TYPE [<- expr] (, ID:TYPE [<- expr])* IN expr
    def _parse_let(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("let")
        bindings = []

        #Primeira declaração (obrigatória)
        try:
            bindings.append(self._parse_let_binding())
        except SyntaxError as e:
            self._registra_erro(str(e))
            self._sincroniza(ate=(",", "in"))

        #Declarações adicionais separadas por vírgula
        while self.ts.is_val(","):
            self.ts.consume()
            try:
                bindings.append(self._parse_let_binding())
            except SyntaxError as e:
                self._registra_erro(str(e))
                self._sincroniza(ate=(",", "in"))

        self.ts.expect_val("in")
        body = self.parse_expr()
        return LetNode(bindings, body, linha)

    def _parse_let_binding(self):
        """Uma declaração dentro do let: ID : TYPE [<- expr]"""
        tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val(":")
        tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        init = None
        if self.ts.is_val("<-"):
            self.ts.consume()
            init = self.parse_expr()
        return LetBindingNode(tok_name[2], tok_type[2], init)

    #case ::= CASE expr OF (ID : TYPE => expr ;)+ ESAC
    def _parse_case(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("case")
        expr = self.parse_expr()
        self.ts.expect_val("of")
        branches = []
        while self.ts.peek() is not None and not self.ts.is_val("esac"):
            try:
                tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
                self.ts.expect_val(":")
                tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
                self.ts.expect_val("=>")
                body = self.parse_expr()
                self.ts.expect_val(";")
                branches.append(CaseBranchNode(tok_name[2], tok_type[2], body))
            except SyntaxError as e:
                self._registra_erro(str(e))
                self._sincroniza(ate=(";", "esac"))
        self.ts.expect_val("esac")
        return CaseNode(expr, branches, linha)

    #arglist ::= ( [expr (, expr)*] )
    def _parse_arglist(self):
        self.ts.expect_val("(")
        args = []
        if not self.ts.is_val(")"):
            args.append(self.parse_expr())
            while self.ts.is_val(","):
                self.ts.consume()
                args.append(self.parse_expr())
        self.ts.expect_val(")")
        return args


def main():
    with open("teste.txt", "r") as arquivo:
        ts = TokenStream(arquivo)
        parser = Parser(ts)
        ast = parser.parse_program()

        if parser.erros:
            print(f"\n{len(parser.erros)} erro(s) encontrado(s):\n")
            for erro in parser.erros:
                print(f"  {erro}")
        else:
            print("Parsing concluído sem erros.")
            print(ast)

if __name__ == "__main__":
    main()