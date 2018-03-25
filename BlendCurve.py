import math
import FreeCAD
import Part
import bsplineBasis

def error(s):
    FreeCAD.Console.PrintError(s)

def knotSeqReverse(knots):
    '''Reverse a knot vector'''
    ma = max(knots)
    mi = min(knots)
    newknots = [ma+mi-k for k in knots]
    newknots.reverse()
    return(newknots)

def knotSeqNormalize(knots):
    '''Normalize a knot vector'''
    ma = max(knots)
    mi = min(knots)
    ran = ma-mi
    newknots = [(k-mi)/ran for k in knots]
    return(newknots)

def knotSeqScale(knots, length):
    '''Scales a knot vector to a given length'''
    ma = max(knots)
    mi = min(knots)
    ran = ma-mi
    newknots = [length * (k-mi)/ran for k in knots]
    return(newknots)

def paramReverse(pa,fp,lp):
    '''Reverse a param in [fp,lp] knot sequence'''
    seq = [fp,pa,lp]
    return(knotSeqReverse(seq)[1])

def bsplineCopy(bs, reverse = False, scale = 1.0):
    '''Copy a BSplineCurve, that can be optionally reversed, and its knotvector normalized'''
    # bs.buildFromPolesMultsKnots
    # poles (sequence of Base.Vector), [mults , knots, periodic, degree, weights (sequence of float), CheckRational]
    mults = bs.getMultiplicities()
    weights = bs.getWeights()
    poles = bs.getPoles()
    knots = bs.getKnots()
    perio = bs.isPeriodic()
    ratio = bs.isRational()
    if scale:
        knots = knotSeqScale(knots, scale)
    if reverse:
        mults.reverse()
        weights.reverse()
        poles.reverse()
        knots = knotSeqReverse(knots)
    bspline = Part.BSplineCurve()
    bspline.buildFromPolesMultsKnots(poles, mults , knots, perio, bs.Degree, weights, ratio)
    return(bspline)

def createKnots(degree, nbPoles):
    if degree >= nbPoles:
        error("createKnots : degree >= nbPoles")
    else:
        nbIntKnots = nbPoles - degree - 1
        start = [0.0 for k in range(degree+1)]
        mid = [float(k) for k in range(1,nbIntKnots+1)]
        end = [float(nbIntKnots+1) for k in range(degree+1)]
        return(start+mid+end)

def createKnotsMults(degree, nbPoles):
    if degree >= nbPoles:
        error("createKnotsMults : degree >= nbPoles")
    else:
        nbIntKnots = nbPoles - degree - 1
        knots = [0.0] + [float(k) for k in range(1,nbIntKnots+1)] + [float(nbIntKnots+1)]
        mults = [degree+1] + [1 for k in range(nbIntKnots)] + [degree+1]
        return(knots, mults)

def curvematch(c1, c2, par1, level=0, scale=1.0):

    c1 = c1.toNurbs()
    c2 = c2.toNurbs()
    len1 = c1.length()
    len2 = c2.length()
    
    c2sta = c2.FirstParameter
    p2 = c2.getPoles()
    seq2 = knotSeqScale(c2.KnotSequence, abs(scale) * len2) #[k*abs(scale) for k in c2.KnotSequence]

    if scale < 0:
        bs1 = bsplineCopy(c1, True, len1)
    else:
        bs1 = bsplineCopy(c1, False, len1)
    pt1 = c1.value(par1)
    par1 = bs1.parameter(pt1)

    p1 = bs1.getPoles()
    #basis1 = splipy.BSplineBasis(order=int(c1.Degree)+1, knots=c1.KnotSequence)
    #basis2 = splipy.BSplineBasis(order=int(c2.Degree)+1, knots=seq)
    basis1 = bsplineBasis.bsplineBasis()
    basis2 = bsplineBasis.bsplineBasis()
    basis1.p = bs1.Degree
    basis1.U = bs1.KnotSequence
    basis2.p = c2.Degree
    basis2.U = seq2

    l = 0
    while l <= level:
        FreeCAD.Console.PrintMessage("\nDerivative %d\n"%l)
        ev1 = basis1.evaluate(par1,d=l) #.A1.tolist()
        ev2 = basis2.evaluate(c2sta,d=l) #.A1.tolist()
        FreeCAD.Console.PrintMessage("Basis %d - %r\n"%(l,ev1))
        FreeCAD.Console.PrintMessage("Basis %d - %r\n"%(l,ev2))
        pole1 = FreeCAD.Vector()
        for i in range(len(ev1)):
            pole1 += 1.0*ev1[i]*p1[i]
        val = ev2[l]
        if val == 0:
            FreeCAD.Console.PrintError("Zero !\n")
            break
        else:
            pole2 = FreeCAD.Vector()
            for i in range(l):
                pole2 += 1.0*ev2[i]*p2[i]
            np = (1.0*pole1-pole2)/val
            FreeCAD.Console.PrintMessage("Moving P%d from (%0.2f,%0.2f,%0.2f) to (%0.2f,%0.2f,%0.2f)\n"%(l,p2[l].x,p2[l].y,p2[l].z,np.x,np.y,np.z))
            p2[l] = np
        l += 1
    nc = c2.copy()
    for i in range(len(p2)):
        nc.setPole(i+1,p2[i])
    return(nc)

class blendCurve:
    def __init__(self, e1 = None, e2 = None):
        if e1 and e2:
            self.edge1 = e1
            self.edge2 = e2
            self.param1 = e1.FirstParameter
            self.param2 = e2.FirstParameter
            self.cont1 = 0
            self.cont2 = 0
            self.scale1 = 1.0
            self.scale2 = 1.0
            self.Curve = Part.BSplineCurve()
            self.getChordLength()
            self.autoScale = True
            self.maxDegree = int(self.Curve.MaxDegree)
        else:
            error("blendCurve initialisation error")
    
    def getChord(self):
        v1 = self.edge1.valueAt(self.param1)
        v2 = self.edge2.valueAt(self.param2)
        ls = Part.LineSegment(v1,v2)
        return(ls)
    
    def getChordLength(self):
        ls = self.getChord()
        self.chordLength = ls.length()
        if self.chordLength < 1e-6:
            error("error : chordLength < 1e-6")
            self.chordLength = 1.0

    def compute(self):
        nbPoles = self.cont1 + self.cont1 + 2
        e = self.getChord()
        poles = e.discretize(nbPoles)
        degree = nbPoles - 1 #max((self.cont1, self.cont2))
        if degree > self.maxDegree:
            degree = self.maxDegree
        #knotSeq = createKnots(degree, nbPoles)
        knots, mults = createKnotsMults(degree, nbPoles)
        weights = [1.0 for k in range(nbPoles)]
        #knotSeq = [0.0 for x in range(nbPoles)]
        #knotSeq2 = [1.0 for x in range(nbPoles)]
        #knotSeq.extend(knotSeq2)
        be = Part.BSplineCurve()
        be.buildFromPolesMultsKnots(poles, mults , knots, False, degree, weights, False)
        #Curve = be.toBSpline()
        nc = curvematch(self.edge1.Curve, be, self.param1, self.cont1, self.scale1)
        rev = bsplineCopy(nc, True, False)
        self.Curve = curvematch(self.edge2.Curve, rev, self.param2, self.cont2, self.scale2)
        #return(self.Curve.getPoles())
        

    def getPolesOld(self): #, edge, param, cont, scale):
        poles1 = []
        poles2 = []
        poles1.append(self.edge1.valueAt(self.param1))
        poles2.append(self.edge2.valueAt(self.param2))
        if self.cont1 > 0:
            t1 = self.edge1.tangentAt(self.param1)
            t1.normalize().multiply(self.unitLength * self.scale1)
            poles1.append(poles1[0].add(t1))
        if self.cont2 > 0:
            t2 = self.edge2.tangentAt(self.param2)
            t2.normalize().multiply(self.unitLength * self.scale2)
            poles2.append(poles2[0].add(t2))
        if self.cont1 > 1:
            curv = self.edge1.curvatureAt(self.param1)
            if curv:
                radius = curv * self.nbSegments * pow(t1.Length,2) / (self.nbSegments -1)
                opp = math.sqrt(abs(pow(self.unitLength * self.scale1,2)-pow(radius,2)))
                c = Part.Circle()
                c.Axis = t1
                v = FreeCAD.Vector(t1)
                v.normalize().multiply(t1.Length+opp)
                c.Center = poles1[0].add(v)
                c.Radius = radius
                plane = Part.Plane(poles1[0],poles1[1],poles1[0].add(self.edge1.normalAt(self.param1)))
                print(plane)
                pt = plane.intersect(c)[0][1] # 2 solutions
                print(pt)
                poles1.append(FreeCAD.Vector(pt.X,pt.Y,pt.Z))
            else:
                poles1.append(poles1[-1].add(t1))
        if self.cont2 > 1:
            curv = self.edge2.curvatureAt(self.param2)
            if curv:
                radius = curv * self.nbSegments * pow(t2.Length,2) / (self.nbSegments -1)
                opp = math.sqrt(abs(pow(self.unitLength * self.scale2,2)-pow(radius,2)))
                c = Part.Circle()
                c.Axis = t2
                v = FreeCAD.Vector(t2)
                v.normalize().multiply(t2.Length+opp)
                c.Center = poles2[0].add(v)
                c.Radius = radius
                plane = Part.Plane(poles2[0],poles2[1],poles2[0].add(self.edge2.normalAt(self.param2)))
                print(plane)
                pt = plane.intersect(c)[0][1] # 2 solutions
                print(pt)
                poles2.append(FreeCAD.Vector(pt.X,pt.Y,pt.Z))
            else:
                poles2.append(poles2[-1].add(t2))
            #if len(poles1) > 1:
                #poles2.append(c.value(c.parameter(poles1[-2])))
            #else:
                #poles2.append(c.value(c.parameter(poles1[0])))
        return(poles1+poles2[::-1])
            
    def getPoles(self):
        self.compute()
        return(self.Curve.getPoles())

    def shape(self):
        self.compute()
        return(self.Curve.toShape())

    def curve(self):
        self.compute()
        return(self.Curve)

#obj1 = App.getDocument("Surface_test_1").getObject("Sphere001")
#e1 = obj1.Shape.Edge2
#e2 = obj1.Shape.Edge4

#bc = blendCurve(e1,e2)
#bc.param1 = e1.LastParameter
#bc.param2 = e2.LastParameter
#bc.cont1 = 2
#bc.cont2 = 2
#bc.scale1 = 1.5
#bc.scale2 = 1.5
#Part.show(bc.shape())

#e = []
#sel = FreeCADGui.Selection.getSelectionEx()
#for selobj in sel:
    #if selobj.HasSubObjects:
        #for sub in selobj.SubObjects:
            #e.append(selobj.Object.Shape)
