from parser import No


#  Gerador de Código
class GeradorGo:
    def __init__(self, ast: No):
        self.ast          = ast
        self.nivel        = 0
        self.usa_fmt      = False
        self.usa_strconv  = False
        self._funcoes     = []
        self._main        = []
        self._destino     = None
        self._tipo_var_atual = None  # tipo da variável sendo declarada (para input)

    # indentação 

    def _indent(self) -> str:
        return "\t" * self.nivel

    def _emit(self, linha: str):
        self._destino.append(self._indent() + linha)

    def _emit_raw(self, linha: str):
        self._destino.append(linha)

    # entrada principal 
    def gerar(self) -> str:
        self._funcoes = []
        self._main    = []
        self._destino = self._main
        self._visitar(self.ast)

        imports = []
        if self.usa_fmt:
            imports.append('\t"fmt"')
        if self.usa_strconv:
            imports.append('\t"strconv"')

        cabecalho = ["package main", ""]
        if imports:
            cabecalho.append("import (")
            cabecalho.extend(imports)
            cabecalho.append(")")
            cabecalho.append("")

        # funções auxiliares de input
        helpers = []
        codigo_gerado = "\n".join(self._funcoes + self._main)
        if "__scanString()" in codigo_gerado:
            helpers += ["func __scanString() string {", '\tvar s string', '\tfmt.Scan(&s)', '\treturn s', "}", ""]
        if "__scanInt()" in codigo_gerado:
            helpers += ["func __scanInt() int {", '\tvar s string', '\tfmt.Scan(&s)', '\tn, _ := strconv.Atoi(s)', '\treturn n', "}", ""]
        if "__scanFloat()" in codigo_gerado:
            helpers += ["func __scanFloat() float64 {", '\tvar s string', '\tfmt.Scan(&s)', '\tf, _ := strconv.ParseFloat(s, 64)', '\treturn f', "}", ""]

        return "\n".join(cabecalho + helpers + self._funcoes + self._main) + "\n"

    # dispatcher 
    def _visitar(self, no: No) -> str:
        metodo = getattr(self, f"_visit_{no.tipo}", self._visit_generico)
        return metodo(no)

    def _visit_generico(self, no: No) -> str:
        for filho in no.filhos:
            self._visitar(filho)
        return ""

    # programa -> main() 
    def _visit_programa(self, no: No):
        self._destino = self._main
        self._emit("func main() {")
        self.nivel += 1
        self._visitar(no.filhos[0])
        self.nivel -= 1
        self._emit("}")

    # bloco 
    def _visit_bloco(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # tipos 
    TIPOS_GO = {
        "cheio"   : "int",
        "quebrada": "float64",
        "papo"    : "string",
    }

    def _tipo_go(self, lexema: str) -> str:
        return self.TIPOS_GO.get(lexema, lexema)

    # declaração 
    # cheio x = 10;  ->  var x int = 10  ou  x := 10

    def _visit_declara(self, no: No):
        no_tipo = no.filhos[0]
        no_id   = no.filhos[1]
        nome    = no_id.valor
        tipo_go = self._tipo_go(no_tipo.valor)

        if len(no.filhos) > 2:
            expr_no = no.filhos[2]
            # se o valor é real/fake, o tipo real em Go é bool
            if expr_no.tipo in ("TRUE", "FALSE"):
                tipo_go = "bool"
            self._tipo_var_atual = tipo_go
            expr = self._expr_str(expr_no)
            self._tipo_var_atual = None
            self._emit(f"var {nome} {tipo_go} = {expr}")
        else:
            self._emit(f"var {nome} {tipo_go}")
            # evita "declared and not used" em Go para vars sem inicialização
            self._emit(f"_ = {nome}")

    # atribuição / sufixo de ID 

    def _visit_cmdSufID_stmt(self, no: No):
        nome = no.filhos[0].valor

        if len(no.filhos) < 2:
            return

        sufixo = no.filhos[1]

        if sufixo.tipo == "args":
            # chamada de função como comando isolado: soma(1, 2);
            # NÃO gera '=' — emite só a chamada
            self.usa_fmt = True
            args = self._args_str(sufixo)
            self._emit(f"{nome}({args})")

        elif sufixo.tipo == "op":
            # i++ ou i--
            self._emit(f"{nome}{sufixo.valor}")

        elif sufixo.tipo == "input":
            # x = mandaopapo()  ->  fmt.Scan(&x)
            self.usa_fmt = True
            self._emit(f"fmt.Scan(&{nome})")

        else:
            # atribuição normal: x = expr
            expr = self._expr_str(sufixo)
            self._emit(f"{nome} = {expr}")

    # print 
    # pprt(x)  ->  fmt.Println(x)

    def _visit_cmdPrint(self, no: No):
        self.usa_fmt = True
        expr = self._expr_str(no.filhos[0])
        self._emit(f"fmt.Println({expr})")

    # input standalone (mandaopapo em atrib) 
    def _visit_input(self, no: No) -> str:
        # tratado em cmdSufID_stmt, não deve aparecer sozinho
        return "/* input */"

    def _visit_cmdIf(self, no: No):
        cond  = self._cond_str(no.filhos[0])
        self._emit(f"if {cond} {{")
        self.nivel += 1
        self._visitar(no.filhos[1])
        self.nivel -= 1

        if len(no.filhos) > 2 and no.filhos[2].tipo != "epsilon":
            self._visit_else_chain(no.filhos[2])
        else:
            self._emit("}")

    def _visit_else_chain(self, no: No):
        if no.tipo == "cmdElseIf":
            cond = self._cond_str(no.filhos[0])
            self._emit(f"}} else if {cond} {{")
            self.nivel += 1
            self._visitar(no.filhos[1])
            self.nivel -= 1
            if len(no.filhos) > 2 and no.filhos[2].tipo != "epsilon":
                self._visit_else_chain(no.filhos[2])
            else:
                self._emit("}")
        elif no.tipo == "cmdElse":
            self._emit("} else {")
            self.nivel += 1
            self._visitar(no.filhos[0])
            self.nivel -= 1
            self._emit("}")
        else:
            self._emit("}")

    def _visit_cmdElseIf(self, no: No):
        pass

    def _visit_cmdElse(self, no: No):
        pass

    def _visit_cmdWhile(self, no: No):
        cond = self._cond_str(no.filhos[0])
        self._emit(f"for {cond} {{")
        self.nivel += 1
        self._visitar(no.filhos[1])
        self.nivel -= 1
        self._emit("}")

    def _visit_cmdFor(self, no: No):
        init   = self._init_for_str(no.filhos[0])
        cond   = self._cond_str(no.filhos[1])
        update = self._update_for_str(no.filhos[2])
        self._emit(f"for {init}; {cond}; {update} {{")
        self.nivel += 1
        self._visitar(no.filhos[3])
        self.nivel -= 1
        self._emit("}")

    def _init_for_str(self, no: No) -> str:
        if no.tipo == "epsilon" or not no.filhos:
            return ""
        if no.filhos[0].tipo == "tipo":
            # cheio i = 0  ->  i := 0  (declaração curta no for)
            nome = no.filhos[1].valor
            val  = self._expr_str(no.filhos[2])
            return f"{nome} := {val}"
        else:
            # i = 0
            nome = no.filhos[0].valor
            val  = self._expr_str(no.filhos[1])
            return f"{nome} = {val}"

    def _update_for_str(self, no: No) -> str:
        if no.tipo == "epsilon" or not no.filhos:
            return ""
        nome = no.filhos[0].valor
        if len(no.filhos) > 1 and no.filhos[1].tipo == "op":
            return f"{nome}{no.filhos[1].valor}"
        elif len(no.filhos) > 1:
            val = self._expr_str(no.filhos[1])
            return f"{nome} = {val}"
        return nome

    # return 
    def _visit_cmdReturn(self, no: No):
        if no.filhos:
            expr = self._expr_str(no.filhos[0])
            self._emit(f"return {expr}")
        else:
            self._emit("return")

    # break / continue 
    def _visit_cmdBreak(self, no: No):
        self._emit("break")

    def _visit_cmdContinue(self, no: No):
        self._emit("continue")

    # função     # missao cheio soma(cheio a, cheio b) { }
    # ->  func soma(a int, b int) int { }

    def _visit_defFuncao(self, no: No):
        no_tipo   = no.filhos[0]
        no_id     = no.filhos[1]
        no_params = no.filhos[2]
        no_corpo  = no.filhos[3]

        tipo_ret = self._tipo_go(no_tipo.valor)
        nome     = no_id.valor
        params   = self._params_str(no_params)

        # se o corpo retorna true/false, o tipo de retorno deve ser bool
        if self._corpo_retorna_bool(no_corpo):
            tipo_ret = "bool"

        # funções são emitidas fora do main
        destino_salvo   = self._destino
        nivel_salvo     = self.nivel
        self._destino   = self._funcoes
        self.nivel      = 0

        self._emit_raw("")
        self._emit(f"func {nome}({params}) {tipo_ret} {{")
        self.nivel += 1
        self._visitar(no_corpo)
        self.nivel -= 1
        self._emit("}")

        self._destino = destino_salvo
        self.nivel    = nivel_salvo

    def _corpo_retorna_bool(self, no: No) -> bool:
        """Verifica recursivamente se algum volta retorna true/false."""
        if no.tipo == "cmdReturn" and no.filhos:
            f = no.filhos[0]
            if f.tipo in ("TRUE", "FALSE"):
                return True
        return any(self._corpo_retorna_bool(f) for f in no.filhos)

    def _cond_str(self, no: No) -> str:
        """Gera a condição sem parênteses externos desnecessários."""
        s = self._expr_str(no)
        if s.startswith("(") and s.endswith(")"):
            return s[1:-1]
        return s

    def _params_str(self, no_params: No) -> str:
        parts = []
        for p in no_params.filhos:
            if p.tipo == "param":
                tipo_go = self._tipo_go(p.filhos[0].valor)
                nome    = p.filhos[1].valor
                parts.append(f"{nome} {tipo_go}")
        return ", ".join(parts)

    # expressões como string 
    def _expr_str(self, no: No) -> str:
        t = no.tipo

        if t == "id":
            return no.valor

        if t == "INT_NUM":
            return no.valor

        if t == "FLOAT_NUM":
            return no.valor

        if t == "STRING":
            return no.valor  # já vem com aspas

        if t == "TRUE":
            return "true"

        if t == "FALSE":
            return "false"

        if t in ("exprAdd", "exprMult", "exprRel", "exprLog"):
            esq = self._expr_str(no.filhos[0])
            dir = self._expr_str(no.filhos[1])
            op  = self._op_go(no.valor)
            return f"({esq} {op} {dir})"

        if t == "exprUnario":
            op   = no.valor
            expr = self._expr_str(no.filhos[0])
            if op == "-":
                return f"(-{expr})"
            if op == "!":
                return f"(!{expr})"
            return expr

        if t == "chamadaFuncao":
            self.usa_fmt = True  # pode precisar de fmt
            nome = no.filhos[0].valor
            args = self._args_str(no.filhos[1])
            return f"{nome}({args})"

        if t == "input":
            self.usa_fmt = True
            tipo = self._tipo_var_atual or "string"
            if tipo == "int":
                self.usa_strconv = True
                return '__scanInt()'
            elif tipo == "float64":
                self.usa_strconv = True
                return '__scanFloat()'
            else:
                return '__scanString()'

        if t == "epsilon":
            return ""

        # fallback
        return f"/* {t} */"

    def _args_str(self, no_args: No) -> str:
        parts = []
        for filho in no_args.filhos:
            if filho.tipo != "epsilon":
                parts.append(self._expr_str(filho))
        return ", ".join(parts)

    def _op_go(self, op: str) -> str:
        mapa = {
            "&&": "&&",
            "||": "||",
            "==": "==",
            "!=": "!=",
            ">":  ">",
            "<":  "<",
            ">=": ">=",
            "<=": "<=",
            "+":  "+",
            "-":  "-",
            "*":  "*",
            "/":  "/",
        }
        return mapa.get(op, op)


#  Ponto de entrada standalone

if __name__ == "__main__":
    import sys
    from lexer import Lexer, imprimir_tokens
    from parser import Parser
    from semantic import AnalisadorSemantico

    if len(sys.argv) < 2:
        print("Uso: python gerador_go.py <arquivo.paulista> [saida.go]")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    SEP = "══════════════════════════════════════"

    # Fase 1 — Léxico
    lexer  = Lexer(codigo)
    tokens = lexer.tokenizar()

    if lexer.erros:
        print(f"{SEP}\n  ERROS LÉXICOS\n{SEP}")
        for e in lexer.erros:
            print(e)
        sys.exit(1)

    # Fase 2 — Sintático
    parser = Parser(tokens, linhas=lexer.linhas)
    ast    = parser.parse()

    if parser.erros:
        print(f"{SEP}\n  ERROS SINTÁTICOS\n{SEP}")
        for e in parser.erros:
            print(e)
        sys.exit(1)

    # Fase 3 — Semântico
    semantico = AnalisadorSemantico(ast, linhas=lexer.linhas)
    ok        = semantico.analisar()

    if not ok:
        print(f"{SEP}\n  ERROS SEMÂNTICOS\n{SEP}")
        for e in semantico.erros:
            print(e)
        sys.exit(1)

    # Fase 4 — Geração de código Go
    gerador  = GeradorGo(ast)
    codigo_go = gerador.gerar()

    print(f"{SEP}\n  CÓDIGO GO GERADO\n{SEP}")
    print(codigo_go)

    # Salva em arquivo se solicitado
    saida = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].replace(".paulista", ".go")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(codigo_go)

    print(f"Arquivo gerado: {saida}")