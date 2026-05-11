from parser import No


#  Tabela de Símbolos com escopos aninhados
class TabelaSimbolos:
    def __init__(self):
        # pilha de escopos: cada escopo é um dict nome → info
        self.pilha = [{}]

    def entrar_escopo(self):
        self.pilha.append({})

    def sair_escopo(self):
        self.pilha.pop()

    def declarar(self, nome: str, tipo: str, linha: int) -> bool:
        """Declara no escopo atual. Retorna False se já existia."""
        escopo_atual = self.pilha[-1]
        if nome in escopo_atual:
            return False  # redeclaração
        escopo_atual[nome] = {"tipo": tipo, "linha": linha}
        return True

    def buscar(self, nome: str) -> dict | None:
        """Busca nos escopos do mais interno ao mais externo."""
        for escopo in reversed(self.pilha):
            if nome in escopo:
                return escopo[nome]
        return None

    def escopo_global(self) -> dict:
        return self.pilha[0]


#  Analisador Semântico
class AnalisadorSemantico:
    def __init__(self, ast: No, linhas: list = None):
        self.ast     = ast
        self.linhas  = linhas or []
        self.tabela  = TabelaSimbolos()
        self.erros   = []
        self.avisos  = []
        # contexto de execução
        self._dentro_funcao = 0   # contador de aninhamento
        self._dentro_laco   = 0   # contador de aninhamento

    # formatação de erro 
    def _erro(self, msg: str, linha: int, lexema: str = ""):
        cabecalho = f"Chapou aqui mano: linha {linha} — {msg}"
        if self.linhas and 1 <= linha <= len(self.linhas):
            trecho = self.linhas[linha - 1]
            col    = trecho.find(lexema) if lexema else 0
            col    = max(col, 0)
            setinha = ' ' * col + '^'
            self.erros.append(f"{cabecalho}\n    {trecho}\n    {setinha}")
        else:
            self.erros.append(cabecalho)

    def _aviso(self, msg: str, linha: int):
        self.avisos.append(f"Aviso: linha {linha} — {msg}")

    # entrada principal 
    def analisar(self):
        self._visitar(self.ast)
        return not self.erros

    # dispatcher 
    def _visitar(self, no: No):
        metodo = getattr(self, f"_visit_{no.tipo}", self._visit_generico)
        metodo(no)

    def _visit_generico(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # programa 
    def _visit_programa(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # bloco 
    def _visit_bloco(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # declaração 
    def _visit_declara(self, no: No):
        # filhos: [tipo, id, (expr opcional)]
        no_tipo = no.filhos[0]
        no_id   = no.filhos[1]
        nome    = no_id.valor
        tipo    = no_tipo.valor
        linha   = no.linha

        ok = self.tabela.declarar(nome, tipo, linha)
        if not ok:
            self._erro(f"variável '{nome}' já foi declarada neste escopo", linha, nome)

        # visita a expressão de inicialização, se houver
        if len(no.filhos) > 2:
            self._visitar(no.filhos[2])

    # uso de identificador 
    def _visit_id(self, no: No):
        nome  = no.valor
        linha = no.linha
        info  = self.tabela.buscar(nome)
        if info is None:
            self._erro(f"variável '{nome}' usada sem ser declarada", linha, nome)

    # auxiliar: valida chamada de função     
    # Reutilizado por _visit_cmdSufID_stmt e _visit_chamadaFuncao
    def _validar_chamada(self, nome: str, no_args: No, linha: int):
        """Verifica se 'nome' é função declarada e se a aridade bate."""
        info = self.tabela.buscar(nome)
        if info is None:
            self._erro(f"função '{nome}' chamada sem ser declarada", linha, nome)
            return
        if not info["tipo"].startswith("funcao:"):
            self._erro(f"'{nome}' não é uma função", linha, nome)
            return
        n_esperado = int(info["tipo"].split(":")[2])
        # conta apenas filhos que não são epsilon
        n_recebido = len([f for f in no_args.filhos if f.tipo != "epsilon"])
        if n_recebido != n_esperado:
            self._erro(
                f"função '{nome}' espera {n_esperado} argumento(s), "
                f"mas recebeu {n_recebido}",
                linha, nome
            )

    # atribuição / sufixo de ID 
    def _visit_cmdSufID_stmt(self, no: No):
        no_id = no.filhos[0]
        nome  = no_id.valor
        linha = no.linha

        if len(no.filhos) < 2:
            return

        sufixo = no.filhos[1]

        if sufixo.tipo == "args":
            # chamada de função como comando: soma(1, 2);
            # não verifica na tabela de variáveis — verifica como função
            self._validar_chamada(nome, sufixo, linha)
            # visita os argumentos para checar uso de variáveis dentro deles
            self._visitar(sufixo)
        else:
            # atribuição, ++ ou -- → nome deve ser variável declarada
            info = self.tabela.buscar(nome)
            if info is None:
                self._erro(f"variável '{nome}' usada sem ser declarada", linha, nome)
            # visita o lado direito (expr, input, op)
            for filho in no.filhos[1:]:
                self._visitar(filho)

    # if / elseif / else 
    def _visit_cmdIf(self, no: No):
        # filhos: [cond, bloco, (elseif|else|epsilon)]
        self._visitar(no.filhos[0])  # condição
        self.tabela.entrar_escopo()
        self._visitar(no.filhos[1])  # bloco then
        self.tabela.sair_escopo()
        if len(no.filhos) > 2:
            self._visitar(no.filhos[2])

    def _visit_cmdElseIf(self, no: No):
        self._visitar(no.filhos[0])  # condição
        self.tabela.entrar_escopo()
        self._visitar(no.filhos[1])  # bloco
        self.tabela.sair_escopo()
        if len(no.filhos) > 2:
            self._visitar(no.filhos[2])

    def _visit_cmdElse(self, no: No):
        self.tabela.entrar_escopo()
        self._visitar(no.filhos[0])
        self.tabela.sair_escopo()

    # while 
    def _visit_cmdWhile(self, no: No):
        self._visitar(no.filhos[0])  # condição
        self._dentro_laco += 1
        self.tabela.entrar_escopo()
        self._visitar(no.filhos[1])  # bloco
        self.tabela.sair_escopo()
        self._dentro_laco -= 1

    # for 
    def _visit_cmdFor(self, no: No):
        # filhos: [initFor, cond, updateFor, bloco]
        self.tabela.entrar_escopo()
        self._visitar(no.filhos[0])  # init (pode declarar var)
        self._visitar(no.filhos[1])  # condição
        self._visitar(no.filhos[2])  # update
        self._dentro_laco += 1
        self._visitar(no.filhos[3])  # bloco
        self._dentro_laco -= 1
        self.tabela.sair_escopo()

    def _visit_initFor(self, no: No):
        # pode ter [tipo, id, expr] ou [id, expr]
        if no.filhos and no.filhos[0].tipo == "tipo":
            no_tipo = no.filhos[0]
            no_id   = no.filhos[1]
            nome    = no_id.valor
            tipo    = no_tipo.valor
            ok = self.tabela.declarar(nome, tipo, no.linha)
            if not ok:
                self._erro(f"variável '{nome}' já foi declarada neste escopo", no.linha, nome)
            if len(no.filhos) > 2:
                self._visitar(no.filhos[2])
        else:
            for filho in no.filhos:
                self._visitar(filho)

    def _visit_updateFor(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # break / continue 
    def _visit_cmdBreak(self, no: No):
        if self._dentro_laco == 0:
            self._erro("'vaza' usado fora de um laço", no.linha, "vaza")

    def _visit_cmdContinue(self, no: No):
        if self._dentro_laco == 0:
            self._erro("'segue' usado fora de um laço", no.linha, "segue")

    # return 
    def _visit_cmdReturn(self, no: No):
        if self._dentro_funcao == 0:
            self._erro("'volta' usado fora de uma função", no.linha, "volta")
        for filho in no.filhos:
            self._visitar(filho)

    # print 
    def _visit_cmdPrint(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # definição de função 
    def _visit_defFuncao(self, no: No):
        # filhos: [tipo, id, params, bloco]
        no_tipo = no.filhos[0]
        no_id   = no.filhos[1]
        nome    = no_id.valor
        linha   = no.linha

        # conta parâmetros para registrar na tabela global
        no_params = no.filhos[2]
        n_params  = len([f for f in no_params.filhos if f.tipo == "param"])

        # registra a função no escopo atual
        ok = self.tabela.declarar(nome, f"funcao:{no_tipo.valor}:{n_params}", linha)
        if not ok:
            self._erro(f"função '{nome}' já foi declarada", linha, nome)

        # novo escopo para corpo da função
        self.tabela.entrar_escopo()
        self._dentro_funcao += 1

        # declara os parâmetros dentro do escopo
        self._visitar(no_params)

        # visita o corpo
        self._visitar(no.filhos[3])

        self._dentro_funcao -= 1
        self.tabela.sair_escopo()

    def _visit_params(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    def _visit_param(self, no: No):
        no_tipo = no.filhos[0]
        no_id   = no.filhos[1]
        ok = self.tabela.declarar(no_id.valor, no_tipo.valor, no.linha)
        if not ok:
            self._erro(f"parâmetro '{no_id.valor}' duplicado", no.linha, no_id.valor)

    # chamada de função (em expressão) 
    def _visit_chamadaFuncao(self, no: No):
        # filhos: [id, args]
        no_id = no.filhos[0]
        nome  = no_id.valor
        linha = no.linha
        no_args = no.filhos[1] if len(no.filhos) > 1 else No("args")
        self._validar_chamada(nome, no_args, linha)
        self._visitar(no_args)

    def _visit_args(self, no: No):
        for filho in no.filhos:
            self._visitar(filho)

    # expressões (visitam filhos normalmente) 
    def _visit_exprLog(self, no: No):
        self._visit_generico(no)

    def _visit_exprRel(self, no: No):
        self._visit_generico(no)

    def _visit_exprAdd(self, no: No):
        self._visit_generico(no)

    def _visit_exprMult(self, no: No):
        self._visit_generico(no)

    def _visit_exprUnario(self, no: No):
        self._visit_generico(no)

    # literais (não precisam de verificação) 
    def _visit_INT_NUM(self, no: No):   pass
    def _visit_FLOAT_NUM(self, no: No): pass
    def _visit_STRING(self, no: No):    pass
    def _visit_TRUE(self, no: No):      pass
    def _visit_FALSE(self, no: No):     pass
    def _visit_tipo(self, no: No):      pass
    def _visit_epsilon(self, no: No):   pass
    def _visit_op(self, no: No):        pass
    def _visit_input(self, no: No):     pass
    def _visit_erro(self, no: No):      pass


#  Ponto de entrada standalone
if __name__ == "__main__":
    import sys
    from lexer import Lexer, imprimir_tokens
    from parser import Parser

    if len(sys.argv) < 2:
        print("Uso: python semantico.py <arquivo.paulista>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    SEP = "══════════════════════════════════════"

    lexer  = Lexer(codigo)
    tokens = lexer.tokenizar()
    imprimir_tokens(tokens)

    if lexer.erros:
        print(f"{SEP}\n  ERROS LÉXICOS\n{SEP}")
        for e in lexer.erros:
            print(e)
        print()

    parser = Parser(tokens, linhas=lexer.linhas)
    ast    = parser.parse()

    print(f"{SEP}\n  ÁRVORE SINTÁTICA (AST)\n{SEP}")
    print(ast)

    if parser.erros:
        print(f"{SEP}\n  ERROS SINTÁTICOS\n{SEP}")
        for e in parser.erros:
            print(e)

    print(f"{SEP}\n  ANÁLISE SEMÂNTICA\n{SEP}")
    semantico = AnalisadorSemantico(ast, linhas=lexer.linhas)
    ok        = semantico.analisar()

    if semantico.avisos:
        for a in semantico.avisos:
            print(a)

    if ok:
        print("Análise semântica concluída sem erros.")
    else:
        for e in semantico.erros:
            print(e)