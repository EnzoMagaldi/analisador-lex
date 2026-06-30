from typing import Dict, Optional, List

from escopo import Escopo
from syntax import (
    AttributeNode, MethodNode,
    AssignNode, DispatchNode, SelfDispatchNode, IfNode, WhileNode,
    BlockNode, LetNode, CaseNode, NewNode, BinOpNode, UnaryOpNode,
    IntNode, StrNode, BoolNode, IdNode
)


class AnalisadorTipo:
    """
    Verifica compatibilidade de tipos e infere o tipo das expressoes.

    A existencia de nomes fica concentrada no AnalisadorEscopo. Aqui, quando um
    nome nao existe no escopo, usamos Object como fallback para continuar a
    analise e descobrir outros erros de tipo no mesmo programa.
    """

    def __init__(self, heranca: Dict, metodos: Dict, atributos: Dict):
        self._heranca = heranca
        self._metodos = metodos
        self._atributos = atributos

        self.erros: List[str] = []
        self._escopo = Escopo()
        self._classe_atual = ""

    def _erro(self, linha: int, msg: str):
        self.erros.append(f"[Linha {linha}] Erro de tipo: {msg}")

    def _tipo_existe(self, tipo: str) -> bool:
        return tipo == "SELF_TYPE" or tipo in self._heranca or tipo in self._metodos

    def _resolve_self_type(self, tipo: str) -> str:
        if tipo == "SELF_TYPE":
            return self._classe_atual
        return tipo

    def _e_subtipo(self, filho: str, ancestral: str) -> bool:
        filho = self._resolve_self_type(filho)
        ancestral = self._resolve_self_type(ancestral)

        atual = filho
        visitados = set()
        while atual is not None:
            if atual == ancestral:
                return True
            if atual in visitados:
                return False
            visitados.add(atual)
            atual = self._heranca.get(atual)
        return False

    def _join(self, t1: str, t2: str) -> str:
        t1 = self._resolve_self_type(t1)
        t2 = self._resolve_self_type(t2)

        if t1 == t2:
            return t1

        ancestrais_t1 = set()
        atual = t1
        while atual is not None:
            ancestrais_t1.add(atual)
            atual = self._heranca.get(atual)

        atual = t2
        while atual is not None:
            if atual in ancestrais_t1:
                return atual
            atual = self._heranca.get(atual)

        return "Object"

    def verifica_programa(self, classes):
        for cls in classes:
            self._verifica_classe(cls)

    def _verifica_classe(self, cls):
        self._classe_atual = cls.name

        if cls.parent and not self._tipo_existe(cls.parent):
            self._erro(
                cls.linha,
                f"Classe '{cls.name}' herda de '{cls.parent}' que nao existe"
            )

        self._escopo.entra()
        self._escopo.define("self", "SELF_TYPE")

        for nome, info in self._atributos.get(cls.name, {}).items():
            self._escopo.define(nome, info.tipo)

        for feat in cls.features:
            if isinstance(feat, AttributeNode):
                self._verifica_atributo(feat)
            elif isinstance(feat, MethodNode):
                self._verifica_metodo(feat)

        self._escopo.sai()

    def _verifica_atributo(self, attr):
        if attr.init is None:
            return

        tipo_init = self._verifica_expr(attr.init)
        if self._tipo_existe(attr.type_) and not self._e_subtipo(tipo_init, attr.type_):
            self._erro(
                attr.linha,
                f"Atributo '{attr.name}': inicializacao tem tipo '{tipo_init}', "
                f"incompativel com '{attr.type_}'"
            )

    def _verifica_metodo(self, met):
        self._escopo.entra()

        for formal in met.formals:
            self._escopo.define(formal.name, formal.type_)

        tipo_body = self._verifica_expr(met.body)

        if self._tipo_existe(met.return_type) and not self._e_subtipo(tipo_body, met.return_type):
            self._erro(
                met.linha,
                f"Metodo '{met.name}': corpo tem tipo '{tipo_body}', "
                f"mas retorno declarado e '{met.return_type}'"
            )

        self._escopo.sai()

    def _verifica_expr(self, no) -> str:
        if isinstance(no, IntNode):
            return "Int"
        if isinstance(no, StrNode):
            return "String"
        if isinstance(no, BoolNode):
            return "Bool"
        if isinstance(no, IdNode):
            return self._verifica_id(no)
        if isinstance(no, AssignNode):
            return self._verifica_assign(no)
        if isinstance(no, BinOpNode):
            return self._verifica_binop(no)
        if isinstance(no, UnaryOpNode):
            return self._verifica_unary(no)
        if isinstance(no, IfNode):
            return self._verifica_if(no)
        if isinstance(no, WhileNode):
            return self._verifica_while(no)
        if isinstance(no, BlockNode):
            return self._verifica_block(no)
        if isinstance(no, LetNode):
            return self._verifica_let(no)
        if isinstance(no, CaseNode):
            return self._verifica_case(no)
        if isinstance(no, NewNode):
            return self._verifica_new(no)
        if isinstance(no, SelfDispatchNode):
            return self._verifica_self_dispatch(no)
        if isinstance(no, DispatchNode):
            return self._verifica_dispatch(no)

        return "Object"

    def _verifica_id(self, no) -> str:
        tipo = self._escopo.busca(no.name)
        if tipo is None:
            return "Object"
        return tipo

    def _verifica_assign(self, no) -> str:
        tipo_var = self._escopo.busca(no.name)
        tipo_val = self._verifica_expr(no.value)

        if tipo_var is not None and not self._e_subtipo(tipo_val, tipo_var):
            self._erro(
                no.linha,
                f"Atribuicao: valor do tipo '{tipo_val}' incompativel com "
                f"'{no.name}' do tipo '{tipo_var}'"
            )

        return tipo_val

    def _verifica_binop(self, no) -> str:
        tl = self._verifica_expr(no.left)
        tr = self._verifica_expr(no.right)

        if no.op in ("+", "-", "*", "/"):
            if tl != "Int":
                self._erro(no.linha, f"Operador '{no.op}': lado esquerdo deve ser Int, encontrado '{tl}'")
            if tr != "Int":
                self._erro(no.linha, f"Operador '{no.op}': lado direito deve ser Int, encontrado '{tr}'")
            return "Int"

        if no.op in ("<", "<="):
            if tl != "Int":
                self._erro(no.linha, f"Operador '{no.op}': lado esquerdo deve ser Int, encontrado '{tl}'")
            if tr != "Int":
                self._erro(no.linha, f"Operador '{no.op}': lado direito deve ser Int, encontrado '{tr}'")
            return "Bool"

        if no.op == "=":
            primitivos = {"Int", "String", "Bool"}
            if (tl in primitivos or tr in primitivos) and tl != tr:
                self._erro(no.linha, f"Igualdade: nao e possivel comparar '{tl}' com '{tr}'")
            return "Bool"

        return "Object"

    def _verifica_unary(self, no) -> str:
        tipo = self._verifica_expr(no.expr)

        if no.op == "~":
            if tipo != "Int":
                self._erro(no.linha, f"Operador '~' exige Int, encontrado '{tipo}'")
            return "Int"

        if no.op == "not":
            if tipo != "Bool":
                self._erro(no.linha, f"Operador 'not' exige Bool, encontrado '{tipo}'")
            return "Bool"

        if no.op == "isvoid":
            return "Bool"

        return "Object"

    def _verifica_if(self, no) -> str:
        tipo_cond = self._verifica_expr(no.cond)
        if tipo_cond != "Bool":
            self._erro(no.linha, f"Condicao do 'if' deve ser Bool, encontrado '{tipo_cond}'")

        tipo_then = self._verifica_expr(no.then_)
        tipo_else = self._verifica_expr(no.else_)
        return self._join(tipo_then, tipo_else)

    def _verifica_while(self, no) -> str:
        tipo_cond = self._verifica_expr(no.cond)
        if tipo_cond != "Bool":
            self._erro(no.linha, f"Condicao do 'while' deve ser Bool, encontrado '{tipo_cond}'")

        self._verifica_expr(no.body)
        return "Object"

    def _verifica_block(self, no) -> str:
        tipo = "Object"
        for expr in no.exprs:
            tipo = self._verifica_expr(expr)
        return tipo

    def _verifica_let(self, no) -> str:
        self._escopo.entra()

        for binding in no.bindings:
            if binding.init is not None:
                tipo_init = self._verifica_expr(binding.init)
                if self._tipo_existe(binding.type_) and not self._e_subtipo(tipo_init, binding.type_):
                    self._erro(
                        no.linha,
                        f"'let': inicializacao de '{binding.name}' tem tipo "
                        f"'{tipo_init}', incompativel com '{binding.type_}'"
                    )
            self._escopo.define(binding.name, binding.type_)

        tipo_body = self._verifica_expr(no.body)
        self._escopo.sai()
        return tipo_body

    def _verifica_case(self, no) -> str:
        self._verifica_expr(no.expr)
        tipos_branches = []
        vistos = set()

        for branch in no.branches:
            if branch.type_ in vistos:
                self._erro(no.linha, f"'case': tipo '{branch.type_}' duplicado nos ramos")
            vistos.add(branch.type_)

            self._escopo.entra()
            self._escopo.define(branch.name, branch.type_)
            tipos_branches.append(self._verifica_expr(branch.body))
            self._escopo.sai()

        if not tipos_branches:
            return "Object"

        resultado = tipos_branches[0]
        for tipo in tipos_branches[1:]:
            resultado = self._join(resultado, tipo)
        return resultado

    def _verifica_new(self, no) -> str:
        if self._tipo_existe(no.type_):
            return no.type_
        return "Object"

    def _verifica_self_dispatch(self, no) -> str:
        return self._verifica_chamada(no.linha, self._classe_atual, no.method, no.args)

    def _verifica_dispatch(self, no) -> str:
        tipo_obj = self._verifica_expr(no.obj)
        tipo_busca = self._resolve_self_type(tipo_obj)

        if no.static_type:
            if not self._tipo_existe(no.static_type):
                self._erro(no.linha, f"Dispatch estatico: tipo '{no.static_type}' nao existe")
            elif not self._e_subtipo(tipo_obj, no.static_type):
                self._erro(
                    no.linha,
                    f"Dispatch estatico: objeto do tipo '{tipo_obj}' nao e "
                    f"subtipo de '{no.static_type}'"
                )
            tipo_busca = no.static_type

        return self._verifica_chamada(no.linha, tipo_busca, no.method, no.args)

    def _verifica_chamada(self, linha: int, tipo_obj: str, nome_met: str, args: list) -> str:
        tipo_obj = self._resolve_self_type(tipo_obj)
        metodos_cls = self._metodos.get(tipo_obj, {})

        if nome_met not in metodos_cls:
            self._erro(linha, f"Metodo '{nome_met}' nao existe em '{tipo_obj}'")
            for arg in args:
                self._verifica_expr(arg)
            return "Object"

        info = metodos_cls[nome_met]

        if len(args) != len(info.params):
            self._erro(
                linha,
                f"Metodo '{nome_met}' em '{tipo_obj}': esperava "
                f"{len(info.params)} argumento(s), recebeu {len(args)}"
            )

        for i, arg in enumerate(args):
            tipo_arg = self._verifica_expr(arg)
            if i >= len(info.params):
                continue

            param_tipo = info.params[i]
            if not self._e_subtipo(tipo_arg, param_tipo):
                self._erro(
                    linha,
                    f"Metodo '{nome_met}': argumento {i + 1} tem tipo "
                    f"'{tipo_arg}', esperado '{param_tipo}'"
                )

        if info.retorno == "SELF_TYPE":
            return tipo_obj
        return info.retorno
