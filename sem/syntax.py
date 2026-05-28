import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Any
from lex import lexico, tipos

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.modules["syntax"] = sys.modules[__name__]

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
        while True:
            tok = lexico(arquivo)
            if tok is None:
                break
            if isinstance(tok, tuple):
                self._tokens.append(tok)

    def peek(self):
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def consume(self):
        tok = self.peek()
        self._pos += 1
        return tok

    def pushback(self):
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
        tok = self.consume()
        if tok is None or tok[2] != valor:
            encontrado = tok[2] if tok else "fim do arquivo"
            linha = tok[0] if tok else "?"
            raise SyntaxError(
                f"[Linha {linha}] Esperado '{valor}', encontrado '{encontrado}'"
            )
        return tok

    def expect_tipo(self, tipo):
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
        self.erros = []

    def _registra_erro(self, mensagem):
        self.erros.append(mensagem)

    def _sincroniza(self, ate=(";")):
        """
        Avança tokens até encontrar um símbolo seguro de retomada (agora funcional).
        """
        prof_chaves   = 0   # rastreia { }
        prof_parenteses = 0 # rastreia ( )

        while self.ts.peek() is not None:
            val = self.ts.peek_val()

            if val == "{":
                prof_chaves += 1
            elif val == "}":
                if prof_chaves > 0:
                    prof_chaves -= 1
                else:
                    if "}" in ate:
                        self.ts.consume()
                        break
                    break
            elif val == "(":
                prof_parenteses += 1
            elif val == ")":
                if prof_parenteses > 0:
                    prof_parenteses -= 1

            if prof_chaves == 0 and prof_parenteses == 0 and val in ate:
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
    def parse_feature(self):
        linha = self.ts.peek_linha()
        try:
            tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
            name = tok_name[2]

            if self.ts.is_val("("):
                return self._parse_method_resto(name, linha)
            else:
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
        self.ts.expect_val(":")
        tok_ret = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val("{")
        body = self.parse_expr()
        self.ts.expect_val("}")
        self.ts.expect_val(";")
        return MethodNode(name, formals, tok_ret[2], body, linha)

    def _parse_formal(self):
        tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val(":")
        tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        return FormalNode(tok_name[2], tok_type[2])

    def parse_expr(self):
        if self.ts.is_tipo(tipos["IDENTIFICADOR"]):
            linha = self.ts.peek_linha()
            tok = self.ts.consume()
            if self.ts.is_val("<-"):
                self.ts.consume()
                value = self.parse_expr()
                return AssignNode(tok[2], value, linha)
            else:
                self.ts.pushback()
        return self.parse_not()

    def parse_not(self):
        if self.ts.is_val("not"):
            linha = self.ts.peek_linha()
            self.ts.consume()
            return UnaryOpNode("not", self.parse_not(), linha)
        return self.parse_compare()

    def parse_compare(self):
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
        tok = self.ts.peek()
        if tok is None:
            raise SyntaxError("Fim inesperado do arquivo")

        val   = tok[2]
        tipo  = tok[1]
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
            if self.ts.is_val("("):
                args = self._parse_arglist()
                return SelfDispatchNode(val, args, linha)
            return IdNode(val, linha)

        raise SyntaxError(f"[Linha {linha}] Token inesperado: '{val}'")

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

    def _parse_while(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("while")
        cond = self.parse_expr()
        self.ts.expect_val("loop")
        body = self.parse_expr()
        self.ts.expect_val("pool")
        return WhileNode(cond, body, linha)

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

    def _parse_let(self):
        linha = self.ts.peek_linha()
        self.ts.expect_val("let")
        bindings = []

        try:
            bindings.append(self._parse_let_binding())
        except SyntaxError as e:
            self._registra_erro(str(e))
            self._sincroniza(ate=(",", "in"))

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
        tok_name = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        self.ts.expect_val(":")
        tok_type = self.ts.expect_tipo(tipos["IDENTIFICADOR"])
        init = None
        if self.ts.is_val("<-"):
            self.ts.consume()
            init = self.parse_expr()
        return LetBindingNode(tok_name[2], tok_type[2], init)

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
    from sem import AnalisadorSemantico
    from escopo import imprimir_ast

    caminho_teste = Path(__file__).with_name("teste.txt")
    with open(caminho_teste, "r") as arquivo:
        ts = TokenStream(arquivo)
        parser = Parser(ts)
        ast = parser.parse_program()

    # erros sintáticos
    if parser.erros:
        print(f"  {len(parser.erros)} erro(s) SINTÁTICO(s):")
        for e in parser.erros:
            print(f"  {e}")
    else:
        print("\n  Análise sintática: OK")

    # análise semântica (só roda se não houver erros sintáticos)
    if not parser.erros:
        semantico = AnalisadorSemantico()
        semantico.analisa(ast)

        if semantico.erros:
            print(f"  {len(semantico.erros)} erro(s) SEMANTICO(s):")
            for e in semantico.erros:
                print(f"  {e}")
        else:
            print("  Análise semântica: OK\n")
            imprimir_ast(ast)

if __name__ == "__main__":
    main()
