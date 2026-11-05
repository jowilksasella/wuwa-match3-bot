"""Rule checks for the solver: python test_solver.py"""
import solver
from vision import ROWS, COLS, G, R, B, W, M, E, ICE, U, X, NONE, HEARTS



def board(cells):
    g = [[(M, W, B, G)[(r * 2 + c) % 4] for c in range(COLS)] for r in range(ROWS)]   # no legal moves
    s = [[NONE] * COLS for _ in range(ROWS)]
    for (r, c), k in cells.items():
        g[r][c] = k
    return g, s


def bottle(g, s, r, c, hearts):
    g[r][c] = E
    s[r][c] = HEARTS + hearts


def main():
    # A step that touches a bottle takes one heart; the last heart removes it.
    g, s = board({})
    bottle(g, s, 3, 3, 3)
    assert solver._hit(g, s, {(3, 4)}) == solver.BOTTLE_HIT and s[3][3] == HEARTS + 2
    g, s = board({})
    bottle(g, s, 3, 3, 1)
    assert solver._hit(g, s, {(2, 3)}) == solver.BOTTLE_HIT + solver.BOTTLE_POP
    assert g[3][3] == solver.EMPTY

    # A diagonal neighbour is not a hit under the orthogonal assumption.
    g, s = board({})
    bottle(g, s, 3, 3, 3)
    assert solver._hit(g, s, {(2, 2)}) == 0

    # Bottles fall with the pieces around them (seen in game).
    g, s = board({})
    bottle(g, s, 2, 3, 3)
    g[3][3] = solver.EMPTY
    solver._gravity(g, s)
    assert g[3][3] == E and s[3][3] == HEARTS + 3

    # Bottles cannot be dragged and never count toward a match.
    g, s = board({(6, 0): R, (6, 1): R})
    bottle(g, s, 6, 2, 3)
    assert solver.simulate(g, s, (6, 2), (5, 2)) is None
    g, s = board({})
    for c in range(3):
        bottle(g, s, 6, c, 3)
    assert not solver._groups(g)

    # The search prefers the match beside a bottle over the same match elsewhere.
    g, s = board({(6, 0): R, (6, 1): R, (5, 2): R,
                  (0, 5): R, (0, 6): R, (1, 7): R})
    bottle(g, s, 5, 1, 3)
    mv, _ = solver.best_move(g, s)
    assert mv in (((5, 2), (6, 2)),), mv
    # One step beside ice removes it; a diagonal step does not.
    g, s = board({(3, 3): ICE})
    assert solver._hit(g, s, {(3, 4)}) == solver.ICE_HIT and g[3][3] == solver.EMPTY
    g, s = board({(3, 3): ICE})
    assert solver._hit(g, s, {(2, 2)}) == 0 and g[3][3] == ICE

    # Ice never falls, holds up what is above it, and cannot be dragged or matched.
    g, s = board({(3, 3): ICE, (4, 3): solver.EMPTY})
    above = g[2][3]
    solver._gravity(g, s)
    assert g[3][3] == ICE and g[2][3] == above and g[4][3] == solver.EMPTY
    g, s = board({(3, 3): ICE})
    assert solver.simulate(g, s, (3, 3), (3, 4)) is None
    g, s = board({(6, 0): ICE, (6, 1): ICE, (6, 2): ICE})
    assert not solver._groups(g)

    # Clearing beside ice scores more than the same clear without it.
    cells = {(6, 0): R, (6, 1): R, (5, 2): R}
    g, s = board(cells)
    plain = solver.simulate(g, s, (5, 2), (6, 2))
    g, s = board({**cells, (5, 0): ICE})
    assert solver.simulate(g, s, (5, 2), (6, 2)) > plain

    print("solver rules ok")


if __name__ == "__main__":
    main()
