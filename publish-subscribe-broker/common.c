

int read_cmd(char bs[])
{
	return bs[0] | bs[1] << 8 | bs[2] << 16 | bs[3] << 24;
}