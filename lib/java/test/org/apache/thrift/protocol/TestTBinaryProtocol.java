package org.apache.thrift.protocol;


public class TestTBinaryProtocol extends ProtocolTestBase {
  @Override
  protected TProtocolFactory getFactory() {
    return new TBinaryProtocol.Factory();
  }

  @Override
  protected boolean canBeUsedNaked() {
    return true;
  }
}
