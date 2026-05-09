from lexer import Lexer, Token, imprimir_tokens


#  Nó da AST
class No:
    """Nó genérico da Árvore Sintática Abstrata (AST)."""
    def __init__(self, tipo: str, filhos: list = None, valor=None, linha: int = 0):
        self.tipo   = tipo
        self.filhos = filhos or []
        self.valor  = valor
        self.linha  = linha

    def __repr__(self, nivel=0):
        indent = "  " * nivel
        s = f"{indent}[{self.tipo}]"
        if self.valor is not None:
            s += f" → '{self.valor}'"
        s += f"  (linha {self.linha})\n" if self.linha else "\n"
        for filho in self.filhos:
            s += filho.__repr__(nivel + 1)
        return s


#  Parser

class Parser:
    def __init__(self, tokens: list, linhas: list = None):
        self.tokens  = tokens
        self.pos     = 0
        self.erros   = []
        self.linhas  = linhas or []  # linhas do código fonte para contexto

    # navegação 

    def atual(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token("EOF", "$", 0)

    def consumir(self, tipo_esperado: str) -> Token:
        tok = self.atual()
        if tok.tipo == tipo_esperado:
            self.pos += 1
            return tok
        self._erro(f"esperado '{tipo_esperado}', encontrado '{tok.lexema}'", tok)
        return tok  # continua mesmo com erro

    def _tipo(self) -> str:
        return self.atual().tipo

    def _erro(self, msg: str, tok: Token = None):
        tok   = tok or self.atual()
        linha = tok.linha
        cabecalho = f"Chapou aqui mano: linha {linha} — {msg}"
        if self.linhas and 1 <= linha <= len(self.linhas):
            trecho  = self.linhas[linha - 1]
            # encontra a coluna do token na linha
            col = trecho.find(tok.lexema)
            col = max(col, 0)
            setinha = ' ' * col + '^'
            self.erros.append(f"{cabecalho}\n    {trecho}\n    {setinha}")
        else:
            self.erros.append(cabecalho)
        # Recuperação de erro: avança um token
        if self._tipo() != "EOF":
            self.pos += 1

    # PROGRAMA     # programa -> PROG_START bloco PROG_END

    def parse(self) -> No:
        no = No("programa", linha=self.atual().linha)
        self.consumir("PROG_START")
        no.filhos.append(self._bloco())
        self.consumir("PROG_END")
        return no

    # BLOCO 
    # bloco -> cmd bloco | epsilon

    INICIO_CMD = {
        "INT_TYPE", "FLOAT_TYPE", "STRING_TYPE",  # declara
        "IF",                                       # cmdIf
        "WHILE",                                    # cmdWhile
        "FOR",                                      # cmdFor
        "PRINT",                                    # cmdPrint
        "RETURN",                                   # cmdReturn
        "BREAK",                                    # cmdBreak
        "CONTINUE",                                 # cmdContinue
        "ID",                                       # cmdSufID_stmt
        "FUNC",                                     # defFuncao
    }

    def _bloco(self) -> No:
        no = No("bloco")
        while self._tipo() in self.INICIO_CMD:
            no.filhos.append(self._cmd())
        return no

    # COMANDO 
    # cmd -> declara | cmdIf | cmdWhile | cmdFor | cmdPrint |
    #        cmdReturn | cmdBreak | cmdContinue | cmdSufID_stmt | defFuncao

    def _cmd(self) -> No:
        t = self._tipo()
        if t in ("INT_TYPE", "FLOAT_TYPE", "STRING_TYPE"):
            return self._declara()
        elif t == "IF":
            return self._cmdIf()
        elif t == "WHILE":
            return self._cmdWhile()
        elif t == "FOR":
            return self._cmdFor()
        elif t == "PRINT":
            return self._cmdPrint()
        elif t == "RETURN":
            return self._cmdReturn()
        elif t == "BREAK":
            return self._cmdBreak()
        elif t == "CONTINUE":
            return self._cmdContinue()
        elif t == "ID":
            return self._cmdSufID_stmt()
        elif t == "FUNC":
            return self._defFuncao()
        else:
            tok = self.atual()
            self._erro(f"comando inválido '{tok.lexema}'", tok)
            return No("erro", linha=tok.linha)

    # DECLARAÇÃO 
    # declara -> tipo ID declaraSuf
    # declaraSuf -> SEMICOLON | ASSIGN expr SEMICOLON

    def _declara(self) -> No:
        linha = self.atual().linha
        tipo_no = self._tipo_var()
        id_tok  = self.consumir("ID")
        no = No("declara", filhos=[tipo_no, No("id", valor=id_tok.lexema, linha=id_tok.linha)], linha=linha)

        if self._tipo() == "SEMICOLON":
            self.consumir("SEMICOLON")
        elif self._tipo() == "ASSIGN":
            self.consumir("ASSIGN")
            no.filhos.append(self._expr())
            self.consumir("SEMICOLON")
        else:
            self._erro("esperado ';' ou '=' após declaração")

        return no

    def _tipo_var(self) -> No:
        tok = self.atual()
        if tok.tipo in ("INT_TYPE", "FLOAT_TYPE", "STRING_TYPE"):
            self.pos += 1
            return No("tipo", valor=tok.lexema, linha=tok.linha)
        self._erro(f"tipo inválido '{tok.lexema}'", tok)
        return No("tipo", valor="?", linha=tok.linha)

    # CMD SUFIXO DE ID     # cmdSufID_stmt -> ID cmdSufID SEMICOLON
    # cmdSufID -> ASSIGN rhs | INCREMENT | DECREMENT | LPAREN args RPAREN

    def _cmdSufID_stmt(self) -> No:
        id_tok = self.consumir("ID")
        no = No("cmdSufID_stmt", linha=id_tok.linha)
        no.filhos.append(No("id", valor=id_tok.lexema, linha=id_tok.linha))

        t = self._tipo()
        if t == "ASSIGN":
            self.consumir("ASSIGN")
            no.filhos.append(self._rhs())
        elif t == "INCREMENT":
            self.consumir("INCREMENT")
            no.filhos.append(No("op", valor="++", linha=self.atual().linha))
        elif t == "DECREMENT":
            self.consumir("DECREMENT")
            no.filhos.append(No("op", valor="--", linha=self.atual().linha))
        elif t == "LPAREN":
            self.consumir("LPAREN")
            no.filhos.append(self._args())
            self.consumir("RPAREN")
        else:
            self._erro(f"esperado '=', '++', '--' ou '(' após ID")

        self.consumir("SEMICOLON")
        return no

    # rhs -> INPUT LPAREN RPAREN | expr
    def _rhs(self) -> No:
        if self._tipo() == "INPUT":
            linha = self.atual().linha
            self.consumir("INPUT")
            self.consumir("LPAREN")
            self.consumir("RPAREN")
            return No("input", linha=linha)
        return self._expr()

    # IF / ELSEIF / ELSE     
    # cmdIf -> IF LPAREN expr RPAREN LBRACE bloco RBRACE cmdElseIf
    # cmdElseIf -> ELSEIF (...) LBRACE bloco RBRACE cmdElseIf | cmdElse | epsilon
    # cmdElse -> ELSE LBRACE bloco RBRACE

    def _cmdIf(self) -> No:
        linha = self.atual().linha
        self.consumir("IF")
        self.consumir("LPAREN")
        cond = self._expr()
        self.consumir("RPAREN")
        self.consumir("LBRACE")
        corpo = self._bloco()
        self.consumir("RBRACE")
        no = No("cmdIf", filhos=[cond, corpo], linha=linha)
        no.filhos.append(self._cmdElseIf())
        return no

    def _cmdElseIf(self) -> No:
        if self._tipo() == "ELSEIF":
            linha = self.atual().linha
            self.consumir("ELSEIF")
            self.consumir("LPAREN")
            cond = self._expr()
            self.consumir("RPAREN")
            self.consumir("LBRACE")
            corpo = self._bloco()
            self.consumir("RBRACE")
            no = No("cmdElseIf", filhos=[cond, corpo], linha=linha)
            no.filhos.append(self._cmdElseIf())
            return no
        elif self._tipo() == "ELSE":
            return self._cmdElse()
        return No("epsilon")

    def _cmdElse(self) -> No:
        linha = self.atual().linha
        self.consumir("ELSE")
        self.consumir("LBRACE")
        corpo = self._bloco()
        self.consumir("RBRACE")
        return No("cmdElse", filhos=[corpo], linha=linha)

    # WHILE 
    # cmdWhile -> WHILE LPAREN expr RPAREN LBRACE bloco RBRACE

    def _cmdWhile(self) -> No:
        linha = self.atual().linha
        self.consumir("WHILE")
        self.consumir("LPAREN")
        cond = self._expr()
        self.consumir("RPAREN")
        self.consumir("LBRACE")
        corpo = self._bloco()
        self.consumir("RBRACE")
        return No("cmdWhile", filhos=[cond, corpo], linha=linha)

    # FOR 
    # cmdFor -> FOR LPAREN initFor SEMICOLON expr SEMICOLON updateFor RPAREN LBRACE bloco RBRACE

    def _cmdFor(self) -> No:
        linha = self.atual().linha
        self.consumir("FOR")
        self.consumir("LPAREN")
        init = self._initFor()
        self.consumir("SEMICOLON")
        cond = self._expr()
        self.consumir("SEMICOLON")
        upd  = self._updateFor()
        self.consumir("RPAREN")
        self.consumir("LBRACE")
        corpo = self._bloco()
        self.consumir("RBRACE")
        return No("cmdFor", filhos=[init, cond, upd, corpo], linha=linha)

    # initFor -> tipo ID ASSIGN expr | ID ASSIGN expr | epsilon
    def _initFor(self) -> No:
        t = self._tipo()
        if t in ("INT_TYPE", "FLOAT_TYPE", "STRING_TYPE"):
            linha = self.atual().linha
            tipo_no = self._tipo_var()
            id_tok  = self.consumir("ID")
            self.consumir("ASSIGN")
            val = self._expr()
            return No("initFor", filhos=[tipo_no, No("id", valor=id_tok.lexema, linha=id_tok.linha), val], linha=linha)
        elif t == "ID":
            linha = self.atual().linha
            id_tok = self.consumir("ID")
            self.consumir("ASSIGN")
            val = self._expr()
            return No("initFor", filhos=[No("id", valor=id_tok.lexema, linha=id_tok.linha), val], linha=linha)
        return No("epsilon")

    # updateFor -> ID ASSIGN expr | ID INCREMENT | ID DECREMENT | epsilon
    def _updateFor(self) -> No:
        if self._tipo() == "ID":
            linha = self.atual().linha
            id_tok = self.consumir("ID")
            t = self._tipo()
            if t == "ASSIGN":
                self.consumir("ASSIGN")
                val = self._expr()
                return No("updateFor", filhos=[No("id", valor=id_tok.lexema, linha=id_tok.linha), val], linha=linha)
            elif t == "INCREMENT":
                self.consumir("INCREMENT")
                return No("updateFor", filhos=[No("id", valor=id_tok.lexema, linha=id_tok.linha), No("op", valor="++")], linha=linha)
            elif t == "DECREMENT":
                self.consumir("DECREMENT")
                return No("updateFor", filhos=[No("id", valor=id_tok.lexema, linha=id_tok.linha), No("op", valor="--")], linha=linha)
        return No("epsilon")

    # PRINT 
    # cmdPrint -> PRINT LPAREN expr RPAREN SEMICOLON

    def _cmdPrint(self) -> No:
        linha = self.atual().linha
        self.consumir("PRINT")
        self.consumir("LPAREN")
        expr = self._expr()
        self.consumir("RPAREN")
        self.consumir("SEMICOLON")
        return No("cmdPrint", filhos=[expr], linha=linha)

    # RETURN     
    # # cmdReturn -> RETURN expr SEMICOLON | RETURN SEMICOLON

    def _cmdReturn(self) -> No:
        linha = self.atual().linha
        self.consumir("RETURN")
        no = No("cmdReturn", linha=linha)
        if self._tipo() != "SEMICOLON":
            no.filhos.append(self._expr())
        self.consumir("SEMICOLON")
        return no

    # BREAK / CONTINUE 
    def _cmdBreak(self) -> No:
        linha = self.atual().linha
        self.consumir("BREAK")
        self.consumir("SEMICOLON")
        return No("cmdBreak", linha=linha)

    def _cmdContinue(self) -> No:
        linha = self.atual().linha
        self.consumir("CONTINUE")
        self.consumir("SEMICOLON")
        return No("cmdContinue", linha=linha)

    # FUNÇÃO     
    # # defFuncao -> FUNC tipo ID LPAREN params RPAREN LBRACE bloco RBRACE

    def _defFuncao(self) -> No:
        linha = self.atual().linha
        self.consumir("FUNC")
        tipo_no = self._tipo_var()
        id_tok  = self.consumir("ID")
        self.consumir("LPAREN")
        params = self._params()
        self.consumir("RPAREN")
        self.consumir("LBRACE")
        corpo = self._bloco()
        self.consumir("RBRACE")
        return No("defFuncao", filhos=[tipo_no, No("id", valor=id_tok.lexema, linha=id_tok.linha), params, corpo], linha=linha)

    # params -> param listaParams | epsilon
    def _params(self) -> No:
        no = No("params")
        if self._tipo() in ("INT_TYPE", "FLOAT_TYPE", "STRING_TYPE"):
            no.filhos.append(self._param())
            no.filhos += self._listaParams()
        return no

    def _listaParams(self) -> list:
        filhos = []
        while self._tipo() == "COMMA":
            self.consumir("COMMA")
            filhos.append(self._param())
        return filhos

    def _param(self) -> No:
        linha = self.atual().linha
        tipo_no = self._tipo_var()
        id_tok  = self.consumir("ID")
        return No("param", filhos=[tipo_no, No("id", valor=id_tok.lexema, linha=id_tok.linha)], linha=linha)

    # args -> expr listaArgs | epsilon
    def _args(self) -> No:
        no = No("args")
        INICIO_EXPR = {"ID", "INT_NUM", "FLOAT_NUM", "STRING", "TRUE", "FALSE", "LPAREN", "NOT", "MINUS"}
        if self._tipo() in INICIO_EXPR:
            no.filhos.append(self._expr())
            while self._tipo() == "COMMA":
                self.consumir("COMMA")
                no.filhos.append(self._expr())
        return no

    # EXPRESSÕES (hierarquia de precedência)
    # expr -> exprLog
    def _expr(self) -> No:
        return self._exprLog()

    # exprLog -> exprRel exprLogSuf
    # exprLogSuf -> AND exprRel exprLogSuf | OR exprRel exprLogSuf | epsilon
    def _exprLog(self) -> No:
        esq = self._exprRel()
        while self._tipo() in ("AND", "OR"):
            op_tok = self.atual()
            self.pos += 1
            dir = self._exprRel()
            esq = No("exprLog", filhos=[esq, dir], valor=op_tok.lexema, linha=op_tok.linha)
        return esq

    # exprRel -> exprAdd exprRelSuf (não associativo)
    # exprRelSuf -> GT|LT|GE|LE|EQ|NE exprAdd | epsilon
    def _exprRel(self) -> No:
        esq = self._exprAdd()
        if self._tipo() in ("GT", "LT", "GE", "LE", "EQ", "NE"):
            op_tok = self.atual()
            self.pos += 1
            dir = self._exprAdd()
            return No("exprRel", filhos=[esq, dir], valor=op_tok.lexema, linha=op_tok.linha)
        return esq

    # exprAdd -> exprMult exprAddSuf
    def _exprAdd(self) -> No:
        esq = self._exprMult()
        while self._tipo() in ("PLUS", "MINUS"):
            op_tok = self.atual()
            self.pos += 1
            dir = self._exprMult()
            esq = No("exprAdd", filhos=[esq, dir], valor=op_tok.lexema, linha=op_tok.linha)
        return esq

    # exprMult -> exprUnario exprMultSuf
    def _exprMult(self) -> No:
        esq = self._exprUnario()
        while self._tipo() in ("MULT", "DIV"):
            op_tok = self.atual()
            self.pos += 1
            dir = self._exprUnario()
            esq = No("exprMult", filhos=[esq, dir], valor=op_tok.lexema, linha=op_tok.linha)
        return esq

    # exprUnario -> NOT exprUnario | MINUS exprUnario | primario
    def _exprUnario(self) -> No:
        if self._tipo() in ("NOT", "MINUS"):
            op_tok = self.atual()
            self.pos += 1
            return No("exprUnario", filhos=[self._exprUnario()], valor=op_tok.lexema, linha=op_tok.linha)
        return self._primario()

    # primario -> ID primarioSuf | INT_NUM | FLOAT_NUM | STRING | TRUE | FALSE | LPAREN expr RPAREN | INPUT LPAREN RPAREN
    def _primario(self) -> No:
        tok = self.atual()
        t   = tok.tipo

        if t == "ID":
            self.pos += 1
            no_id = No("id", valor=tok.lexema, linha=tok.linha)
            # primarioSuf -> LPAREN args RPAREN | epsilon
            if self._tipo() == "LPAREN":
                self.consumir("LPAREN")
                args = self._args()
                self.consumir("RPAREN")
                return No("chamadaFuncao", filhos=[no_id, args], linha=tok.linha)
            return no_id

        elif t == "INPUT":
            # mandaopapo() como expressão: cheio n = mandaopapo();
            self.consumir("INPUT")
            self.consumir("LPAREN")
            self.consumir("RPAREN")
            return No("input", linha=tok.linha)

        elif t in ("INT_NUM", "FLOAT_NUM", "STRING", "TRUE", "FALSE"):
            self.pos += 1
            return No(t, valor=tok.lexema, linha=tok.linha)

        elif t == "LPAREN":
            self.consumir("LPAREN")
            no = self._expr()
            self.consumir("RPAREN")
            return no

        else:
            self._erro(f"expressão inválida: '{tok.lexema}'", tok)
            return No("erro", linha=tok.linha)


#  Ponto de entrada standalone
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python parser.py <arquivo.paulista>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    # Fase 1 — Léxico
    lexer  = Lexer(codigo)
    tokens = lexer.tokenizar()
    imprimir_tokens(tokens)

    if lexer.erros:
        print("══════════════════════════════════════")
        print("  ERROS LÉXICOS")
        print("══════════════════════════════════════")
        for e in lexer.erros:
            print(e)
        print()

    # Fase 2 — Sintático
    parser = Parser(tokens, linhas=lexer.linhas)
    ast    = parser.parse()

    print("══════════════════════════════════════")
    print("  ÁRVORE SINTÁTICA (AST)")
    print("══════════════════════════════════════")
    print(ast)

    if parser.erros:
        print("══════════════════════════════════════")
        print("  ERROS SINTÁTICOS")
        print("══════════════════════════════════════")
        for e in parser.erros:
            print(e)
    else:
        print("Análise sintática concluída sem erros.")