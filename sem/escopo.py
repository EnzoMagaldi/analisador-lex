from dataclasses import dataclass, field
from typing import Optional, Dict, List

from syntax import (
    ProgramNode, ClassNode, AttributeNode, MethodNode, FormalNode,
    AssignNode, DispatchNode, SelfDispatchNode, IfNode, WhileNode,
    BlockNode, LetBindingNode, LetNode, CaseBranchNode, CaseNode,
    NewNode, BinOpNode, UnaryOpNode, IntNode, StrNode, BoolNode, IdNode,
)

@dataclass
class InfoMetodo:
    nome: str
    params: List[str]
    retorno: str
    classe: str
    linha: int

@dataclass
class InfoAtributo:
    nome: str
    tipo: str
    classe: str
    linha: int


class Escopo:
    def __init__(self):
        self._pilha: List[Dict[str, str]] = [{}]

    def entra(self):
        self._pilha.append({})

    def sai(self):
        if len(self._pilha) > 1:
            self._pilha.pop()

    def define(self, nome: str, tipo: str):
        self._pilha[-1][nome] = tipo

    def busca(self, nome: str) -> Optional[str]:
        for tabela in reversed(self._pilha):
            if nome in tabela:
                return tabela[nome]
        return None
    

class AnalisadorEscopo:
    '''
    garante que todo nome referenciado existe no contexto atual
    não verifica se os tipos são compatíveis
    '''

    def __init__(self, heranca: Dict, metodos: Dict, atributos: Dict):
        
        self._heranca   = heranca
        self._metodos   = metodos
        self._atributos = atributos

        self.erros: List[str] = []
        self._escopo = Escopo()
        self._classe_atual = ""

    def _erro(self, linha: int, msg: str):
        self.erros.append(f"[Linha {linha}] Erro de escopo: {msg}")

    def _tipo_existe(self, tipo: str) -> bool:
        return tipo in self._heranca or tipo in self._metodos

    def verifica_programa(self, classes):
        for cls in classes:
            self._verifica_classe(cls)

    def _verifica_classe(self, cls):
        from syntax import AttributeNode, MethodNode
        self._classe_atual = cls.name

        self._escopo.entra()
        self._escopo.define("self", cls.name)

        # coloca atributos da classe no escopo
        for nome, info in self._atributos.get(cls.name, {}).items():
            if not self._tipo_existe(info.tipo):
                self._erro(info.linha,
                    f"Tipo '{info.tipo}' do atributo '{nome}' não existe")
            self._escopo.define(nome, info.tipo)

        for feat in cls.features:
            if isinstance(feat, MethodNode):
                self._verifica_metodo(feat)
            elif isinstance(feat, AttributeNode):
                self._verifica_atributo_corpo(feat)

        self._escopo.sai()

    def _verifica_atributo_corpo(self, attr):
        """Verifica se o corpo da inicialização usa nomes válidos."""
        if attr.init is not None:
            self._verifica_expr_escopo(attr.init)

    def _verifica_metodo(self, met):
        # verifica se os tipos dos parâmetros existem
        self._escopo.entra()
        for formal in met.formals:
            if not self._tipo_existe(formal.type_):
                self._erro(met.linha,
                    f"Tipo '{formal.type_}' do parâmetro '{formal.name}' "
                    f"no método '{met.name}' não existe")
            self._escopo.define(formal.name, formal.type_)

        # verifica o tipo de retorno
        if not self._tipo_existe(met.return_type):
            self._erro(met.linha,
                f"Tipo de retorno '{met.return_type}' do método "
                f"'{met.name}' não existe")

        self._verifica_expr_escopo(met.body)
        self._escopo.sai()

    # verificação de escopo nas expressões

    def _verifica_expr_escopo(self, no):
        from syntax import (
            IdNode, AssignNode, BinOpNode, UnaryOpNode, IfNode, WhileNode,
            BlockNode, LetNode, CaseNode, NewNode, SelfDispatchNode,
            DispatchNode, IntNode, StrNode, BoolNode
        )

        if isinstance(no, (IntNode, StrNode, BoolNode)):
            return   # literais não referenciam nomes

        if isinstance(no, IdNode):
            if self._escopo.busca(no.name) is None:
                self._erro(no.linha,
                    f"Variável '{no.name}' não declarada")

        elif isinstance(no, AssignNode):
            if self._escopo.busca(no.name) is None:
                self._erro(no.linha,
                    f"Atribuição a variável '{no.name}' não declarada")
            self._verifica_expr_escopo(no.value)

        elif isinstance(no, BinOpNode):
            self._verifica_expr_escopo(no.left)
            self._verifica_expr_escopo(no.right)

        elif isinstance(no, UnaryOpNode):
            self._verifica_expr_escopo(no.expr)

        elif isinstance(no, IfNode):
            self._verifica_expr_escopo(no.cond)
            self._verifica_expr_escopo(no.then_)
            self._verifica_expr_escopo(no.else_)

        elif isinstance(no, WhileNode):
            self._verifica_expr_escopo(no.cond)
            self._verifica_expr_escopo(no.body)

        elif isinstance(no, BlockNode):
            for expr in no.exprs:
                self._verifica_expr_escopo(expr)

        elif isinstance(no, LetNode):
            self._escopo.entra()
            for binding in no.bindings:
                if not self._tipo_existe(binding.type_):
                    self._erro(no.linha,
                        f"Tipo '{binding.type_}' da variável "
                        f"'{binding.name}' no 'let' não existe")
                if binding.init is not None:
                    self._verifica_expr_escopo(binding.init)
                self._escopo.define(binding.name, binding.type_)
            self._verifica_expr_escopo(no.body)
            self._escopo.sai()

        elif isinstance(no, CaseNode):
            self._verifica_expr_escopo(no.expr)
            for branch in no.branches:
                if not self._tipo_existe(branch.type_):
                    self._erro(no.linha,
                        f"Tipo '{branch.type_}' no 'case' não existe")
                self._escopo.entra()
                self._escopo.define(branch.name, branch.type_)
                self._verifica_expr_escopo(branch.body)
                self._escopo.sai()

        elif isinstance(no, NewNode):
            if not self._tipo_existe(no.type_):
                self._erro(no.linha, f"'new': tipo '{no.type_}' não existe")

        elif isinstance(no, SelfDispatchNode):
            metodos_cls = self._metodos.get(self._classe_atual, {})
            if no.method not in metodos_cls:
                self._erro(no.linha,
                    f"Método '{no.method}' não existe em "
                    f"'{self._classe_atual}'")
            for arg in no.args:
                self._verifica_expr_escopo(arg)

        elif isinstance(no, DispatchNode):
            self._verifica_expr_escopo(no.obj)
            for arg in no.args:
                self._verifica_expr_escopo(arg)

def imprimir_ast(no, prefixo="", ultimo=True):
    if no is None:
        return
    conector  = "└─ " if ultimo else "├─ "
    extensao  = "   " if ultimo else "│  "

    if isinstance(no, IntNode):
        print(f"{prefixo}{conector}Int({no.value})")
        return
    if isinstance(no, StrNode):
        print(f"{prefixo}{conector}Str(\"{no.value}\")")
        return
    if isinstance(no, BoolNode):
        print(f"{prefixo}{conector}Bool({no.value})")
        return
    if isinstance(no, IdNode):
        print(f"{prefixo}{conector}Id({no.name})")
        return
    if isinstance(no, ProgramNode):
        print(f"{prefixo}{conector}Program")
        for i, c in enumerate(no.classes):
            imprimir_ast(c, prefixo + extensao, i == len(no.classes) - 1)
    elif isinstance(no, ClassNode):
        heranca = f" extends {no.parent}" if no.parent else ""
        print(f"{prefixo}{conector}Class {no.name}{heranca}  [linha {no.linha}]")
        for i, f in enumerate(no.features):
            imprimir_ast(f, prefixo + extensao, i == len(no.features) - 1)
    elif isinstance(no, MethodNode):
        params = ", ".join(f"{f.name}:{f.type_}" for f in no.formals)
        print(f"{prefixo}{conector}Method {no.name}({params}) : {no.return_type}  [linha {no.linha}]")
        imprimir_ast(no.body, prefixo + extensao, True)
    elif isinstance(no, AttributeNode):
        print(f"{prefixo}{conector}Attribute {no.name} : {no.type_}  [linha {no.linha}]")
        if no.init:
            imprimir_ast(no.init, prefixo + extensao, True)
    elif isinstance(no, AssignNode):
        print(f"{prefixo}{conector}Assign {no.name}  [linha {no.linha}]")
        imprimir_ast(no.value, prefixo + extensao, True)
    elif isinstance(no, BinOpNode):
        print(f"{prefixo}{conector}BinOp '{no.op}'  [linha {no.linha}]")
        imprimir_ast(no.left,  prefixo + extensao, False)
        imprimir_ast(no.right, prefixo + extensao, True)
    elif isinstance(no, UnaryOpNode):
        print(f"{prefixo}{conector}UnaryOp '{no.op}'  [linha {no.linha}]")
        imprimir_ast(no.expr, prefixo + extensao, True)
    elif isinstance(no, IfNode):
        print(f"{prefixo}{conector}If  [linha {no.linha}]")
        print(f"{prefixo}{extensao}├─ cond:")
        imprimir_ast(no.cond,  prefixo + extensao + "│  ", True)
        print(f"{prefixo}{extensao}├─ then:")
        imprimir_ast(no.then_, prefixo + extensao + "│  ", True)
        print(f"{prefixo}{extensao}└─ else:")
        imprimir_ast(no.else_, prefixo + extensao + "   ", True)
    elif isinstance(no, WhileNode):
        print(f"{prefixo}{conector}While  [linha {no.linha}]")
        print(f"{prefixo}{extensao}├─ cond:")
        imprimir_ast(no.cond, prefixo + extensao + "│  ", True)
        print(f"{prefixo}{extensao}└─ body:")
        imprimir_ast(no.body, prefixo + extensao + "   ", True)
    elif isinstance(no, BlockNode):
        print(f"{prefixo}{conector}Block  [linha {no.linha}]")
        for i, e in enumerate(no.exprs):
            imprimir_ast(e, prefixo + extensao, i == len(no.exprs) - 1)
    elif isinstance(no, LetNode):
        print(f"{prefixo}{conector}Let  [linha {no.linha}]")
        for b in no.bindings:
            print(f"{prefixo}{extensao}├─ binding {b.name} : {b.type_}")
            if b.init:
                imprimir_ast(b.init, prefixo + extensao + "│  ", True)
        print(f"{prefixo}{extensao}└─ in:")
        imprimir_ast(no.body, prefixo + extensao + "   ", True)
    elif isinstance(no, CaseNode):
        print(f"{prefixo}{conector}Case  [linha {no.linha}]")
        print(f"{prefixo}{extensao}├─ expr:")
        imprimir_ast(no.expr, prefixo + extensao + "│  ", True)
        for i, b in enumerate(no.branches):
            ultimo_b = i == len(no.branches) - 1
            print(f"{prefixo}{extensao}{'└─' if ultimo_b else '├─'} branch {b.name} : {b.type_}")
            imprimir_ast(b.body, prefixo + extensao + ("   " if ultimo_b else "│  "), True)
    elif isinstance(no, NewNode):
        print(f"{prefixo}{conector}New {no.type_}  [linha {no.linha}]")
    elif isinstance(no, DispatchNode):
        static = f"@{no.static_type}" if no.static_type else ""
        print(f"{prefixo}{conector}Dispatch {static}.{no.method}  [linha {no.linha}]")
        imprimir_ast(no.obj, prefixo + extensao, len(no.args) == 0)
        for i, a in enumerate(no.args):
            imprimir_ast(a, prefixo + extensao, i == len(no.args) - 1)
    elif isinstance(no, SelfDispatchNode):
        print(f"{prefixo}{conector}SelfDispatch {no.method}  [linha {no.linha}]")
        for i, a in enumerate(no.args):
            imprimir_ast(a, prefixo + extensao, i == len(no.args) - 1)