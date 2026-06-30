from escopo import AnalisadorEscopo, InfoMetodo, InfoAtributo
from tipo import AnalisadorTipo

HERANCA_PADRAO = {
    "Int": "Object", "String": "Object", "Bool": "Object",
    "IO":  "Object", "Object": None,
}

class AnalisadorSemantico:
    def __init__(self):
        self.erros = []
        self._heranca   = dict(HERANCA_PADRAO)
        self._metodos   = self._metodos_padrao()
        self._atributos = self._atributos_padrao()

    def _metodos_padrao(self):
        return {
            "Object": {
                "abort": InfoMetodo("abort", [], "Object", "Object", 0),
                "type_name": InfoMetodo("type_name", [], "String", "Object", 0),
                "copy": InfoMetodo("copy", [], "SELF_TYPE", "Object", 0),
            },
            "IO": {
                "out_string": InfoMetodo("out_string", ["String"], "SELF_TYPE", "IO", 0),
                "out_int": InfoMetodo("out_int", ["Int"], "SELF_TYPE", "IO", 0),
                "in_string": InfoMetodo("in_string", [], "String", "IO", 0),
                "in_int": InfoMetodo("in_int", [], "Int", "IO", 0),
            },
            "String": {
                "length": InfoMetodo("length", [], "Int", "String", 0),
                "concat": InfoMetodo("concat", ["String"], "String", "String", 0),
                "substr": InfoMetodo("substr", ["Int", "Int"], "String", "String", 0),
            },
            "Int": {},
            "Bool": {},
        }

    def _atributos_padrao(self):
        return {
            "Object": {},
            "IO": {},
            "String": {},
            "Int": {},
            "Bool": {},
        }

    def analisa(self, programa):
        self._coleta_previa(programa)

        analisador_escopo = AnalisadorEscopo(self._heranca, self._metodos, self._atributos)
        analisador_escopo.verifica_programa(programa.classes)
        self.erros += analisador_escopo.erros

        analisador_tipo = AnalisadorTipo(self._heranca, self._metodos, self._atributos)
        analisador_tipo.verifica_programa(programa.classes)
        self.erros += analisador_tipo.erros

    def _coleta_previa(self, programa):
        from syntax import MethodNode, AttributeNode
        for cls in programa.classes:
            self._heranca[cls.name]   = cls.parent if cls.parent else "Object"
            self._metodos[cls.name]   = {}
            self._atributos[cls.name] = {}
        for cls in programa.classes:
            for feat in cls.features:
                if isinstance(feat, MethodNode):
                    self._metodos[cls.name][feat.name] = InfoMetodo(
                        nome=feat.name,
                        params=[f.type_ for f in feat.formals],
                        retorno=feat.return_type,
                        classe=cls.name, linha=feat.linha)
                elif isinstance(feat, AttributeNode):
                    self._atributos[cls.name][feat.name] = InfoAtributo(
                        nome=feat.name, tipo=feat.type_,
                        classe=cls.name, linha=feat.linha)
        for cls in programa.classes:
            self._herda_features(cls.name)

    def _herda_features(self, nome_cls, visitados=None):
        if visitados is None:
            visitados = set()
        if nome_cls in visitados:
            return
        visitados.add(nome_cls)
        pai = self._heranca.get(nome_cls)
        if pai and pai in self._metodos:
            self._herda_features(pai, visitados)
            for nome, info in self._metodos[pai].items():
                if nome not in self._metodos[nome_cls]:
                    self._metodos[nome_cls][nome] = info
            for nome, info in self._atributos.get(pai, {}).items():
                if nome not in self._atributos[nome_cls]:
                    self._atributos[nome_cls][nome] = info
