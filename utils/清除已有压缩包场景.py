#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL执行器 - 命令行版本
"""

import pymysql
import time


class SQLExecutorCLI:
    def __init__(self):
        # 数据库连接信息
        self.db_info = {
            'host': 'rm-uf6mp542d72149yf80o.mysql.rds.aliyuncs.com',
            'user': 'root',
            'password': 'Znzmo19121@',
            'db': 'znzmo',
            'charset': 'utf8mb4',
            'connect_timeout': 5
        }

        # SQL语句列表
        self.sql_statements = [

            "DELETE FROM commodity_upload_package_hash;"

        ]

    def print_header(self):
        """打印程序头部信息"""
        print("=" * 60)
        print("SQL执行器 - 命令行版本")
        print("=" * 60)
        print(f"数据库: {self.db_info['host']}")
        print(f"数据库名: {self.db_info['db']}")
        print(f"SQL语句数量: {len(self.sql_statements)}")
        print("=" * 60)

    def get_account_id(self):
        """获取用户输入的账户ID"""
        while True:
            account_id = input("\n请输入账户ID: ").strip()
            if account_id:
                # 确认用户输入
                confirm = input(f"确认要执行账户ID '{account_id}' 的SQL吗? (y/n): ").strip().lower()
                if confirm in ['y', 'yes', '是', 'Y']:
                    return account_id
                else:
                    print("已取消，请重新输入账户ID")
            else:
                print("账户ID不能为空，请重新输入")

    def execute_sql(self, account_id):
        """执行SQL语句"""
        print(f"\n开始执行SQL，账户ID: {account_id}")
        print("正在连接数据库...")

        try:
            # 连接数据库
            connection = pymysql.connect(**self.db_info)
            cursor = connection.cursor()

            print("✓ 数据库连接成功！")
            print(f"准备执行 {len(self.sql_statements)} 条SQL语句...")
            print("-" * 60)

            success_count = 0
            error_count = 0

            for i, sql_template in enumerate(self.sql_statements, 1):
                try:
                    # 替换SQL中的账户ID
                    sql = sql_template.format(account_id=account_id)

                    print(f"[{i:2d}/{len(self.sql_statements)}] 执行: {sql}")

                    # 执行SQL
                    cursor.execute(sql)

                    if sql.strip().upper().startswith('SELECT'):
                        result = cursor.fetchall()
                        print(f"    结果: {result}")
                    else:
                        affected_rows = cursor.rowcount
                        print(f"    影响行数: {affected_rows}")

                    success_count += 1
                    print(f"    ✓ 执行成功")

                except Exception as e:
                    error_count += 1
                    print(f"    ✗ 执行失败: {str(e)}")

                print()  # 空行分隔

                # 短暂延迟
                time.sleep(0.1)

            # 提交事务
            connection.commit()

            # 关闭连接
            cursor.close()
            connection.close()

            # 显示执行结果
            print("=" * 60)
            print("SQL执行完成！")
            print(f"成功: {success_count} 条")
            print(f"失败: {error_count} 条")
            print("=" * 60)

            if error_count == 0:
                print("🎉 所有SQL执行成功！")
            else:
                print("⚠️  部分SQL执行失败，请检查错误信息")

        except Exception as e:
            print(f"❌ 数据库连接失败: {str(e)}")
            print("请检查网络连接和数据库配置")

    def run(self):
        """运行程序"""
        try:
            self.print_header()

            while True:
                account_id = self.get_account_id()
                self.execute_sql(account_id)

                # 询问是否继续
                continue_exec = input("\n是否继续执行其他账户ID? (y/n): ").strip().lower()
                if continue_exec not in ['y', 'yes', '是', 'Y']:
                    break

            print("\n程序结束，感谢使用！")

        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
        except Exception as e:
            print(f"\n程序运行出错: {e}")


def main():
    """主函数"""
    try:
        executor = SQLExecutorCLI()
        executor.run()
    except Exception as e:
        print(f"程序启动失败: {e}")
        input("按回车键退出...")


if __name__ == "__main__":
    main()
