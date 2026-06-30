import argparse
import json
from pathlib import Path

import lex
from sem import AnalisadorSemantico
from syntax import (
    AssignNode,
    BinOpNode,
    BlockNode,
    BoolNode,
    ClassNode,
    IdNode,
    IfNode,
    IntNode,
    LetNode,
    MethodNode,
    Parser,
    ProgramNode,
    StrNode,
    TokenStream,
    UnaryOpNode,
    WhileNode,
)


class ErroGeracaoCodigo(Exception):
    pass


class GeradorBril:
    """
    Gera Bril core a partir do subconjunto de COOL ja aceito pelo parser.

    A representacao principal e JSON, porque e o formato consumido pelo
    interpretador de Bril. O formato textual e emitido como conveniencia para
    uso com bril2json.
    """

    OPS_BINARIAS = {
        "+": "add",
        "-": "sub",
        "*": "mul",
        "/": "div",
        "<": "lt",
        "<=": "le",
        "=": "eq",
    }

    def __init__(self):
        self.funcoes = []
        self.instrs = []
        self.ambientes = []
        self.tmp = 0
        self.label = 0

    def gerar_programa(self, programa: ProgramNode) -> dict:
        self.funcoes = []
        for classe in programa.classes:
            self._gerar_classe(classe)
        return {"functions": self.funcoes}

    def _gerar_classe(self, classe: ClassNode):
        for feature in classe.features:
            if isinstance(feature, MethodNode):
                self._gerar_metodo(classe, feature)

    def _gerar_metodo(self, classe: ClassNode, metodo: MethodNode):
        self.instrs = []
        self.ambientes = [{}]
        self.tmp = 0
        self.label = 0

        args = []
        for formal in metodo.formals:
            tipo = self._tipo_bril(formal.type_)
            args.append({"name": formal.name, "type": tipo})
            self._define(formal.name, formal.name)

        resultado = self._gerar_expr(metodo.body)
        eh_main = classe.name == "Main" and metodo.name == "main"
        if resultado is None:
            self.instrs.append({"op": "ret"})
        else:
            if eh_main:
                self.instrs.append({"op": "print", "args": [resultado]})
            self.instrs.append({"op": "ret", "args": [resultado]})

        nome = "main" if eh_main else f"{classe.name}_{metodo.name}"
        funcao = {
            "name": nome,
            "args": args,
            "instrs": self.instrs,
        }
        retorno = self._tipo_bril(metodo.return_type, permitir_object=True)
        if retorno is not None:
            funcao["type"] = retorno
        self.funcoes.append(funcao)

    def _gerar_expr(self, no):
        if isinstance(no, IntNode):
            dest = self._novo_tmp()
            self.instrs.append({"op": "const", "dest": dest, "type": "int", "value": no.value})
            return dest

        if isinstance(no, BoolNode):
            dest = self._novo_tmp()
            self.instrs.append({"op": "const", "dest": dest, "type": "bool", "value": no.value})
            return dest

        if isinstance(no, StrNode):
            raise ErroGeracaoCodigo(
                f"[Linha {no.linha}] Bril core nao possui tipo String; "
                "remova strings ou estenda o runtime."
            )

        if isinstance(no, IdNode):
            var = self._busca(no.name)
            if var is None:
                raise ErroGeracaoCodigo(f"[Linha {no.linha}] Variavel '{no.name}' sem valor gerado")
            return var

        if isinstance(no, AssignNode):
            valor = self._gerar_expr(no.value)
            self._atribui(no.name, valor)
            return valor

        if isinstance(no, BinOpNode):
            return self._gerar_binop(no)

        if isinstance(no, UnaryOpNode):
            return self._gerar_unary(no)

        if isinstance(no, BlockNode):
            valor = None
            for expr in no.exprs:
                valor = self._gerar_expr(expr)
            return valor

        if isinstance(no, LetNode):
            return self._gerar_let(no)

        if isinstance(no, IfNode):
            return self._gerar_if(no)

        if isinstance(no, WhileNode):
            return self._gerar_while(no)

        nome = type(no).__name__
        linha = getattr(no, "linha", "?")
        raise ErroGeracaoCodigo(f"[Linha {linha}] Geracao Bril ainda nao suporta {nome}")

    def _gerar_binop(self, no: BinOpNode):
        esq = self._gerar_expr(no.left)
        dir_ = self._gerar_expr(no.right)
        dest = self._novo_tmp()
        op = self.OPS_BINARIAS[no.op]
        tipo = "bool" if no.op in ("<", "<=", "=") else "int"
        self.instrs.append({"op": op, "dest": dest, "type": tipo, "args": [esq, dir_]})
        return dest

    def _gerar_unary(self, no: UnaryOpNode):
        valor = self._gerar_expr(no.expr)
        dest = self._novo_tmp()

        if no.op == "~":
            zero = self._const_int(0)
            self.instrs.append({"op": "sub", "dest": dest, "type": "int", "args": [zero, valor]})
            return dest

        if no.op == "not":
            verdadeiro = self._const_bool(True)
            self.instrs.append({"op": "eq", "dest": dest, "type": "bool", "args": [valor, verdadeiro]})
            negado = self._novo_tmp()
            falso = self._const_bool(False)
            self.instrs.append({"op": "eq", "dest": negado, "type": "bool", "args": [dest, falso]})
            return negado

        if no.op == "isvoid":
            self.instrs.append({"op": "const", "dest": dest, "type": "bool", "value": False})
            return dest

        raise ErroGeracaoCodigo(f"[Linha {no.linha}] Operador unario '{no.op}' sem traducao")

    def _gerar_let(self, no: LetNode):
        self._entra_escopo()
        for binding in no.bindings:
            if binding.init is not None:
                valor = self._gerar_expr(binding.init)
            else:
                valor = self._valor_padrao(binding.type_)
            self._define(binding.name, valor)
        resultado = self._gerar_expr(no.body)
        self._sai_escopo()
        return resultado

    def _gerar_if(self, no: IfNode):
        cond = self._gerar_expr(no.cond)
        entao = self._novo_label("then")
        senao = self._novo_label("else")
        fim = self._novo_label("endif")
        resultado = self._novo_tmp()

        self.instrs.append({"op": "br", "args": [cond], "labels": [entao, senao]})
        self.instrs.append({"label": entao})
        valor_entao = self._gerar_expr(no.then_)
        self.instrs.append({"op": "id", "dest": resultado, "type": "int", "args": [valor_entao]})
        self.instrs.append({"op": "jmp", "labels": [fim]})

        self.instrs.append({"label": senao})
        valor_senao = self._gerar_expr(no.else_)
        self.instrs.append({"op": "id", "dest": resultado, "type": "int", "args": [valor_senao]})
        self.instrs.append({"op": "jmp", "labels": [fim]})

        self.instrs.append({"label": fim})
        return resultado

    def _gerar_while(self, no: WhileNode):
        inicio = self._novo_label("while")
        corpo = self._novo_label("body")
        fim = self._novo_label("endwhile")

        self.instrs.append({"label": inicio})
        cond = self._gerar_expr(no.cond)
        self.instrs.append({"op": "br", "args": [cond], "labels": [corpo, fim]})
        self.instrs.append({"label": corpo})
        self._gerar_expr(no.body)
        self.instrs.append({"op": "jmp", "labels": [inicio]})
        self.instrs.append({"label": fim})
        return self._const_int(0)

    def _valor_padrao(self, tipo_cool: str):
        if tipo_cool == "Bool":
            return self._const_bool(False)
        if tipo_cool == "Int":
            return self._const_int(0)
        raise ErroGeracaoCodigo(f"Inicializacao padrao para '{tipo_cool}' ainda nao suportada em Bril")

    def _const_int(self, valor: int):
        dest = self._novo_tmp()
        self.instrs.append({"op": "const", "dest": dest, "type": "int", "value": valor})
        return dest

    def _const_bool(self, valor: bool):
        dest = self._novo_tmp()
        self.instrs.append({"op": "const", "dest": dest, "type": "bool", "value": valor})
        return dest

    def _novo_tmp(self):
        nome = f"v{self.tmp}"
        self.tmp += 1
        return nome

    def _novo_label(self, prefixo: str):
        nome = f"{prefixo}_{self.label}"
        self.label += 1
        return nome

    def _entra_escopo(self):
        self.ambientes.append({})

    def _sai_escopo(self):
        self.ambientes.pop()

    def _define(self, nome: str, valor: str):
        self.ambientes[-1][nome] = valor

    def _atribui(self, nome: str, valor: str):
        for ambiente in reversed(self.ambientes):
            if nome in ambiente:
                ambiente[nome] = valor
                return
        self._define(nome, valor)

    def _busca(self, nome: str):
        for ambiente in reversed(self.ambientes):
            if nome in ambiente:
                return ambiente[nome]
        return None

    def _tipo_bril(self, tipo_cool: str, permitir_object=False):
        if tipo_cool == "Int":
            return "int"
        if tipo_cool == "Bool":
            return "bool"
        if permitir_object and tipo_cool in ("Object", "SELF_TYPE", "IO"):
            return None
        raise ErroGeracaoCodigo(f"Tipo COOL '{tipo_cool}' ainda nao tem representacao em Bril core")


def programa_para_bril_texto(programa_bril: dict) -> str:
    linhas = []
    for funcao in programa_bril["functions"]:
        args = ", ".join(f"{arg['name']}: {arg['type']}" for arg in funcao.get("args", []))
        retorno = f": {funcao['type']} " if "type" in funcao else " "
        linhas.append(f"@{funcao['name']}({args}){retorno}" + "{")
        for instr in funcao["instrs"]:
            linhas.append("  " + _instr_para_texto(instr))
        linhas.append("}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"


def _instr_para_texto(instr: dict) -> str:
    if "label" in instr:
        return f".{instr['label']}:"

    op = instr["op"]
    args = " ".join(instr.get("args", []))
    labels = " ".join(f".{label}" for label in instr.get("labels", []))

    if op == "const":
        valor = instr["value"]
        if isinstance(valor, bool):
            valor = "true" if valor else "false"
        return f"{instr['dest']}: {instr['type']} = const {valor};"

    if "dest" in instr:
        partes = [op]
        if args:
            partes.append(args)
        return f"{instr['dest']}: {instr['type']} = {' '.join(partes)};"

    partes = [op]
    if args:
        partes.append(args)
    if labels:
        partes.append(labels)
    return f"{' '.join(partes)};"


def carregar_cool(caminho: Path) -> ProgramNode:
    lex.lst_read = None
    lex.linha = 1
    with open(caminho, "r", encoding="utf-8") as arquivo:
        ts = TokenStream(arquivo)
        parser = Parser(ts)
        ast = parser.parse_program()

    if parser.erros:
        erros = "\n".join(parser.erros)
        raise ErroGeracaoCodigo(f"Erros sintaticos impedem geracao de codigo:\n{erros}")

    semantico = AnalisadorSemantico()
    semantico.analisa(ast)
    if semantico.erros:
        erros = "\n".join(semantico.erros)
        raise ErroGeracaoCodigo(f"Erros semanticos impedem geracao de codigo:\n{erros}")

    return ast


def gerar_de_arquivo(caminho: Path, formato: str) -> str:
    ast = carregar_cool(caminho)
    programa_bril = GeradorBril().gerar_programa(ast)
    if formato == "json":
        return json.dumps(programa_bril, indent=2, ensure_ascii=False) + "\n"
    if formato == "bril":
        return programa_para_bril_texto(programa_bril)
    raise ErroGeracaoCodigo(f"Formato desconhecido: {formato}")


def main():
    parser = argparse.ArgumentParser(
        description="Gera codigo Bril a partir de um programa COOL."
    )
    parser.add_argument("entrada", nargs="?", default="teste3.cool", help="arquivo .cool de entrada")
    parser.add_argument(
        "-f",
        "--formato",
        choices=("json", "bril"),
        default="bril",
        help="formato de saida: 'json' para brili ou 'bril' para usar com bril2json",
    )
    parser.add_argument("-o", "--saida", help="arquivo de saida; se omitido, imprime no terminal")
    args = parser.parse_args()

    try:
        saida = gerar_de_arquivo(Path(args.entrada), args.formato)
    except ErroGeracaoCodigo as erro:
        raise SystemExit(str(erro))

    if args.saida:
        Path(args.saida).write_text(saida, encoding="utf-8")
    else:
        print(saida, end="")


if __name__ == "__main__":
    main()
