from SimpleLangParser import SimpleLangParser
from SimpleLangVisitor import SimpleLangVisitor
from custom_types import IntType, FloatType, StringType, BoolType

class TypeCheckVisitor(SimpleLangVisitor):

  def visitMulDiv(self, ctx: SimpleLangParser.MulDivContext):
    left_type = self.visit(ctx.expr(0))
    right_type = self.visit(ctx.expr(1))
    
    if isinstance(left_type, (IntType, FloatType)) and isinstance(right_type, (IntType, FloatType)):
        return FloatType() if isinstance(left_type, FloatType) or isinstance(right_type, FloatType) else IntType()
    else:
        raise TypeError("Unsupported operand types for * or /: {} and {}".format(left_type, right_type))

  def visitAddSub(self, ctx: SimpleLangParser.AddSubContext):
    left_type = self.visit(ctx.expr(0))
    right_type = self.visit(ctx.expr(1))
    
    if isinstance(left_type, (IntType, FloatType)) and isinstance(right_type, (IntType, FloatType)):
        return FloatType() if isinstance(left_type, FloatType) or isinstance(right_type, FloatType) else IntType()
    else:
        raise TypeError("Unsupported operand types for + or -: {} and {}".format(left_type, right_type))
  
  def visitInt(self, ctx: SimpleLangParser.IntContext):
    return IntType()

  def visitFloat(self, ctx: SimpleLangParser.FloatContext):
    return FloatType()

  def visitString(self, ctx: SimpleLangParser.StringContext):
    return StringType()

  def visitBool(self, ctx: SimpleLangParser.BoolContext):
    return BoolType()

  def visitComparison(self, ctx: SimpleLangParser.ComparisonContext):
    left_type = self.visit(ctx.expr(0))
    right_type = self.visit(ctx.expr(1))
    
    if isinstance(left_type, StringType) and not isinstance(right_type, StringType):
        raise TypeError("Cannot compare string with {}: {} {} {}".format(right_type, left_type, ctx.op.text, right_type))
    
    if (isinstance(left_type, BoolType) and isinstance(right_type, (IntType, FloatType))) or \
       (isinstance(left_type, (IntType, FloatType)) and isinstance(right_type, BoolType)):
        if ctx.op.text not in ['==', '!=']:
            raise TypeError("Cannot use {} operator between {} and {}".format(ctx.op.text, left_type, right_type))
    
    return BoolType()

  def visitLogicalOp(self, ctx: SimpleLangParser.LogicalOpContext):
    left_type = self.visit(ctx.expr(0))
    right_type = self.visit(ctx.expr(1))
    
    if not isinstance(left_type, BoolType) or not isinstance(right_type, BoolType):
        raise TypeError("Logical operators {} require boolean operands, got {} and {}".format(ctx.op.text, left_type, right_type))
    
    return BoolType()

  def visitParens(self, ctx: SimpleLangParser.ParensContext):
    return self.visit(ctx.expr())
